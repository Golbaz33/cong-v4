# Fichier : ui/forms/conge_form.py
# Version 4.2 : Adaptée au nouveau CongeManager et au système de soldes.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sqlite3
import logging
from datetime import datetime

# Import des composants de l'architecture
from core.conges.strategies import (
    CongeAnnuelStrategy, CongeMaladieStrategy, CongeMaterniteStrategy,
    CongePaterniteStrategy, CongeCalendaireStrategy
)
from ui.widgets.date_picker import DatePickerWindow
from utils.date_utils import validate_date, format_date_for_display, calculate_reprise_date
from utils.config_loader import CONFIG

class CongeForm(tk.Toplevel):
    STRATEGIES = {
        "Congé annuel": CongeAnnuelStrategy(),
        "Congé exceptionnel": CongeCalendaireStrategy(),
        "Congé de maladie": CongeMaladieStrategy(),
        "Congé de maternité": CongeMaterniteStrategy(),
        "Congé de paternité": CongePaterniteStrategy(),
    }

    def __init__(self, parent, manager, agent_id, conge_id=None):
        super().__init__(parent)
        self.parent = parent
        self.manager = manager
        self.agent_id = agent_id
        self.conge_id = conge_id
        self.is_modification = conge_id is not None
        
        self.current_strategy = None
        self.original_cert_path = None
        
        # --- Récupération de l'agent et de l'année d'exercice ---
        agent_data = self.manager.get_agent_by_id(self.agent_id)
        self.agent_ppr = agent_data.ppr
        agent_name = f"{agent_data.nom} {agent_data.prenom}"
        self.agent_solde_total = agent_data.get_solde_total_actif()

        # NOTE : Récupération de l'année d'exercice depuis une source fiable
        # Idéalement, le manager devrait avoir une méthode get_annee_exercice()
        self.annee_exercice = datetime.now().year
        # -----------------------------------------------------------
        
        title = f"Modifier un Congé - {agent_name}" if self.is_modification else f"Ajouter un Congé - {agent_name}"
        self.title(title)
        self.grab_set()
        self.resizable(False, False)

        self._create_variables()
        self._create_widgets()
        self._load_interim_agents()
        
        if self.is_modification:
            self._populate_data()
        else:
            self.type_var.set("Congé annuel")

    def _create_variables(self):
        self.type_var = tk.StringVar()
        self.days_var = tk.StringVar(value='1')
        self.interim_var = tk.StringVar()
        self.cert_path_var = tk.StringVar()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        # --- Cadre d'information sur le solde ---
        solde_info_frame = ttk.Frame(main_frame, relief="groove", padding=5)
        solde_info_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(solde_info_frame, text="Solde Annuel Actif Total :", font=('Helvetica', 10, 'bold')).pack(side="left")
        ttk.Label(solde_info_frame, text=f"{self.agent_solde_total:.1f} jours", font=('Helvetica', 10)).pack(side="left", padx=5)

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill="x")
        
        labels = ["Type de congé:", "Date de début:", "Durée (jours):", "Date de fin:", "Date de reprise:", "Justification:", "Intérimaire:"]
        for i, text in enumerate(labels):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, sticky="w", padx=5, pady=8)

        self.type_combo = ttk.Combobox(form_frame, textvariable=self.type_var, values=list(self.STRATEGIES.keys()), state="readonly", width=38)
        self.type_combo.grid(row=0, column=1, sticky="ew", columnspan=2)
        
        self.start_date_entry = ttk.Entry(form_frame, width=30)
        self.start_date_entry.grid(row=1, column=1)
        ttk.Button(form_frame, text="📅", width=2, command=lambda: DatePickerWindow(self, self.start_date_entry, self.manager, self.type_var.get())).grid(row=1, column=2)

        self.days_spinbox = ttk.Spinbox(form_frame, from_=0, to=365, textvariable=self.days_var, width=10, command=self._update_end_date_from_days)
        self.days_spinbox.grid(row=2, column=1, sticky="w")
        
        self.end_date_entry = ttk.Entry(form_frame, width=30)
        self.end_date_entry.grid(row=3, column=1)
        ttk.Button(form_frame, text="📅", width=2, command=lambda: DatePickerWindow(self, self.end_date_entry, self.manager, self.type_var.get())).grid(row=3, column=2)

        self.reprise_date_entry = ttk.Entry(form_frame, width=30, state="readonly")
        self.reprise_date_entry.grid(row=4, column=1, columnspan=2, sticky="ew")

        self.justif_entry = ttk.Entry(form_frame, width=40)
        self.justif_entry.grid(row=5, column=1, columnspan=2, sticky="ew")

        self.interim_combo = ttk.Combobox(form_frame, textvariable=self.interim_var, state="readonly", width=38)
        self.interim_combo.grid(row=6, column=1, columnspan=2, sticky="ew")

        self.cert_frame = ttk.LabelFrame(main_frame, text="Certificat Médical", padding=10)
        self.cert_file_label = ttk.Label(self.cert_frame, text="Aucun fichier attaché.", anchor="w", wraplength=350)
        self.cert_file_label.pack(fill="x", pady=(0, 5))
        cert_btn_frame = ttk.Frame(self.cert_frame)
        cert_btn_frame.pack(fill="x")
        ttk.Button(cert_btn_frame, text="Attacher un fichier...", command=self._attach_certificate).pack(side="left")
        self.remove_cert_btn = ttk.Button(cert_btn_frame, text="Supprimer le justificatif", command=self._remove_certificate)
        self.remove_cert_btn.pack(side="left", padx=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(20, 0))
        ttk.Button(btn_frame, text="Valider", command=self._on_validate).pack(side="right")
        ttk.Button(btn_frame, text="Annuler", command=self.destroy).pack(side="right", padx=10)

        self.type_var.trace_add("write", lambda *args: self._on_type_change())
        self.start_date_entry.bind("<FocusOut>", lambda e: self.after(100, self._update_end_date_from_days))
        self.start_date_entry.bind("<<DatePicked>>", lambda e: self.after(100, self._update_end_date_from_days))
        self.days_spinbox.bind("<FocusOut>", lambda e: self.after(100, self._update_end_date_from_days))
        self.days_spinbox.bind("<Return>", lambda e: self.after(100, self._update_end_date_from_days))
        self.end_date_entry.bind("<FocusOut>", lambda e: self.after(100, self._update_days_from_dates))
        self.end_date_entry.bind("<<DatePicked>>", lambda e: self.after(100, self._update_days_from_dates))

    def _on_type_change(self, event=None):
        type_conge = self.type_var.get()
        if not type_conge: return
        self.current_strategy = self.STRATEGIES[type_conge]
        self.current_strategy.configure_ui(self)
        self.after(100, self._update_end_date_from_days)

    def _update_end_date_from_days(self):
        try:
            days = int(self.days_var.get())
            start_date = validate_date(self.start_date_entry.get())
            if not start_date or days < 0: 
                self._update_reprise_date(); return
            holidays_set = self.manager.get_holidays_set_for_period(start_date.year, start_date.year + 2)
            end_date = self.current_strategy.calculate_end_date(start_date, days, holidays_set)
            current_state = self.end_date_entry.cget('state')
            self.end_date_entry.config(state="normal")
            self.end_date_entry.delete(0, tk.END)
            self.end_date_entry.insert(0, end_date.strftime("%d/%m/%Y"))
            self.end_date_entry.config(state=current_state)
            self._update_reprise_date()
        except (ValueError, TypeError): 
            self._update_reprise_date(); return

    def _update_days_from_dates(self):
        try:
            start_date = validate_date(self.start_date_entry.get())
            end_date = validate_date(self.end_date_entry.get())
            if not start_date or not end_date or end_date < start_date: 
                self.days_var.set("0"); self._update_reprise_date(); return
            holidays_set = self.manager.get_holidays_set_for_period(start_date.year, end_date.year)
            days = self.current_strategy.calculate_days(start_date, end_date, holidays_set)
            current_state = self.days_spinbox.cget('state')
            self.days_spinbox.config(state="normal")
            self.days_var.set(str(days))
            self.days_spinbox.config(state=current_state)
            self._update_reprise_date()
        except (ValueError, TypeError): 
            self.days_var.set("0"); self._update_reprise_date()

    def _update_reprise_date(self):
        self.reprise_date_entry.config(state="normal")
        self.reprise_date_entry.delete(0, tk.END)
        end_date = validate_date(self.end_date_entry.get())
        if end_date:
            holidays_set = self.manager.get_holidays_set_for_period(end_date.year, end_date.year + 1)
            reprise = calculate_reprise_date(end_date, holidays_set)
            if reprise:
                self.reprise_date_entry.insert(0, reprise.strftime("%d/%m/%Y"))
        self.reprise_date_entry.config(state="readonly")

    def _populate_data(self):
        conge = self.manager.get_conge_by_id(self.conge_id)
        if not conge:
            messagebox.showerror("Erreur", "Congé introuvable.", parent=self)
            self.destroy(); return
        self.type_var.set(conge.type_conge)
        self.start_date_entry.insert(0, format_date_for_display(conge.date_debut.strftime('%Y-%m-%d')))
        self.end_date_entry.insert(0, format_date_for_display(conge.date_fin.strftime('%Y-%m-%d')))
        self.justif_entry.insert(0, conge.justif or "")
        self.days_var.set(str(conge.jours_pris))
        self.after(100, self._update_reprise_date)
        if conge.interim_id:
            for name, id_ in self.interim_agents.items():
                if id_ == conge.interim_id:
                    self.interim_var.set(name); break

    def _load_interim_agents(self):
        agents = self.manager.get_all_agents(exclude_id=self.agent_id)
        self.interim_agents = {f"{a.nom} {a.prenom} (PPR: {a.ppr})": a.id for a in agents}
        self.interim_combo['values'] = [""] + sorted(list(self.interim_agents.keys()))

    def _attach_certificate(self):
        filetypes = CONFIG.get('ui', {}).get('certificat_file_types', [("Tous les fichiers", "*.*")])
        filepath = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if filepath:
            self.cert_path_var.set(filepath)
            self.current_strategy._update_certificat_display(self)
            
    def _remove_certificate(self):
        if messagebox.askyesno("Confirmation", "Supprimer le justificatif attaché ?", parent=self):
            self.cert_path_var.set("")
            self.current_strategy._update_certificat_display(self)
    
    def _on_validate(self):
        try:
            # On prépare le dictionnaire de données pour le manager
            form_data = {
                'agent_id': self.agent_id, 'agent_ppr': self.agent_ppr,
                'conge_id': self.conge_id, 'type_conge': self.type_var.get(),
                'date_debut': self.start_date_entry.get(), 'date_fin': self.end_date_entry.get(),
                'jours_pris': int(self.days_var.get()), 'justif': self.justif_entry.get().strip(),
                'interim_id': self.interim_agents.get(self.interim_var.get()),
                'cert_path': self.cert_path_var.get(), 'original_cert_path': self.original_cert_path,
                'annee_exercice': self.annee_exercice # On transmet l'année d'exercice
            }
            
            # On appelle la nouvelle méthode centralisée du manager
            success = self.manager.handle_conge_submission(form_data, self.is_modification)
            
            if success:
                message = "Congé modifié." if self.is_modification else "Congé ajouté."
                self.parent.set_status(message)
                self.parent.refresh_all(self.agent_id)
                self.destroy()

        except (ValueError, sqlite3.Error) as e:
            messagebox.showerror("Erreur de Validation", str(e), parent=self)
        except Exception as e:
            logging.error(f"Erreur inattendue dans le formulaire de congé: {e}", exc_info=True)
            messagebox.showerror("Erreur Inattendue", f"Une erreur imprévue est survenue: {e}", parent=self)