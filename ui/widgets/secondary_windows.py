# Fichier : ui/widgets/secondary_windows.py
# Version finale intégrant toutes les améliorations et fonctionnalités.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import holidays
import sqlite3
import threading

from ui.widgets.date_picker import DatePickerWindow
from utils.date_utils import validate_date, format_date_for_display
from utils.config_loader import CONFIG

class HolidaysManagerWindow(tk.Toplevel):
    def __init__(self, parent, conge_manager):
        super().__init__(parent)
        self.manager = conge_manager
        
        self.title("Gestion des Jours Fériés")
        self.grab_set()
        self.resizable(False, False)

        self._create_widgets()
        self.refresh_holidays_list()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True)
        top_frame = ttk.LabelFrame(main_frame, text="Jours Fériés Enregistrés"); top_frame.pack(fill="x", expand=True, pady=5, padx=5)
        year_frame = ttk.Frame(top_frame, padding=5); year_frame.pack(fill="x")
        ttk.Label(year_frame, text="Année:").pack(side="left")
        current_year = datetime.now().year
        self.year_var = tk.StringVar(value=str(current_year))
        self.year_spinbox = ttk.Spinbox(year_frame, from_=current_year - 5, to=current_year + 5, textvariable=self.year_var, width=8, command=self.refresh_holidays_list)
        self.year_spinbox.pack(side="left", padx=5)
        cols = ("Date", "Description", "Type"); self.holidays_tree = ttk.Treeview(top_frame, columns=cols, show="headings", height=10)
        for col in cols: self.holidays_tree.heading(col, text=col)
        self.holidays_tree.column("Date", width=100, anchor="center"); self.holidays_tree.column("Description", width=250); self.holidays_tree.column("Type", width=100, anchor="center")
        self.holidays_tree.pack(fill="x", expand=True, padx=5, pady=5)
        self.holidays_tree.bind("<<TreeviewSelect>>", self._on_holiday_select)
        btn_frame = ttk.Frame(top_frame); btn_frame.pack(padx=5, pady=(0, 5), fill="x")
        self.modify_button = ttk.Button(btn_frame, text="Modifier Description", command=self.modify_selected_holiday, state="disabled"); self.modify_button.pack(side="left", expand=True, fill="x", padx=2)
        self.delete_button = ttk.Button(btn_frame, text="Supprimer", command=self.delete_selected_holiday, state="disabled"); self.delete_button.pack(side="left", expand=True, fill="x", padx=2)
        self.actions_frame = ttk.LabelFrame(main_frame, text="Actions"); self.actions_frame.pack(fill="x", expand=True, pady=5, padx=5)
        ttk.Button(self.actions_frame, text="Restaurer les jours automatiques pour cette année", command=self.restore_auto_holidays).pack(side="top", fill="x", padx=5, pady=5)
        ttk.Button(self.actions_frame, text="Vérifier la cohérence des congés annuels", command=self.audit_annual_leaves).pack(side="top", fill="x", padx=5, pady=5)
        bottom_frame = ttk.LabelFrame(main_frame, text="Ajouter un Jour Férié Personnalisé"); bottom_frame.pack(fill="x", expand=True, pady=5, padx=5)
        add_frame = ttk.Frame(bottom_frame, padding=5); add_frame.pack()
        ttk.Label(add_frame, text="Date:").grid(row=0, column=0, sticky="w", pady=2); self.date_entry = ttk.Entry(add_frame, width=15); self.date_entry.grid(row=0, column=1, padx=5)
        ttk.Button(add_frame, text="📅", width=2, command=lambda: DatePickerWindow(self, self.date_entry, self.manager)).grid(row=0, column=2)
        ttk.Label(add_frame, text="Description:").grid(row=1, column=0, sticky="w", pady=2); self.desc_entry = ttk.Entry(add_frame, width=30); self.desc_entry.grid(row=1, column=1, columnspan=2, padx=5)
        ttk.Button(bottom_frame, text="Ajouter ce jour férié", command=self.add_holiday).pack(pady=5)

    def audit_annual_leaves(self):
        try: year = int(self.year_var.get())
        except ValueError: messagebox.showerror("Année invalide", "Veuillez entrer une année valide.", parent=self); return
        messagebox.showinfo("Analyse en cours", f"Vérification des congés pour {year}...\nL'interface peut sembler inactive, mais le travail se fait en arrière-plan.", parent=self)
        self.config(cursor="watch")
        for child in self.actions_frame.winfo_children(): child.config(state="disabled")
        result_container = []
        def task_wrapper():
            try: result_container.append(self.manager.find_inconsistent_annual_leaves(year))
            except Exception as e: result_container.append(e)
        worker_thread = threading.Thread(target=task_wrapper); worker_thread.start()
        self._check_audit_completion(worker_thread, result_container)

    def _check_audit_completion(self, thread, result_container):
        if thread.is_alive():
            self.after(100, lambda: self._check_audit_completion(thread, result_container))
        else:
            self.config(cursor="")
            for child in self.actions_frame.winfo_children(): child.config(state="normal")
            result = result_container[0] if result_container else None
            if isinstance(result, Exception): messagebox.showerror("Erreur d'audit", f"Une erreur est survenue: {result}", parent=self)
            elif not result: messagebox.showinfo("Rapport d'audit", f"Aucune incohérence trouvée pour l'année analysée.", parent=self)
            else: ReportWindow(self, int(self.year_var.get()), result)

    def refresh_holidays_list(self):
        for row in self.holidays_tree.get_children(): self.holidays_tree.delete(row)
        try:
            year = int(self.year_var.get()); all_holidays = self.manager.get_holidays_for_year(str(year))
            for h_date, h_name, h_type in all_holidays: self.holidays_tree.insert("", "end", values=(format_date_for_display(h_date), h_name, h_type))
        except (tk.TclError, ValueError): pass
        except Exception as e: messagebox.showerror("Erreur Inattendue", f"Impossible de charger les jours fériés: {e}", parent=self)
        self._on_holiday_select()

    def add_holiday(self):
        date_str = self.date_entry.get(); desc = self.desc_entry.get().strip(); validated_date = validate_date(date_str)
        if not validated_date or not desc: messagebox.showerror("Erreur", "Veuillez entrer une date valide et une description.", parent=self); return
        date_sql = validated_date.strftime("%Y-%m-%d")
        if self.manager.add_holiday(date_sql, desc, "Personnalisé"): self.desc_entry.delete(0, tk.END); self.date_entry.delete(0, tk.END); self.refresh_holidays_list()
        else: messagebox.showerror("Erreur", "Cette date est déjà enregistrée.", parent=self)

    def _on_holiday_select(self, event=None):
        new_state = "normal" if self.holidays_tree.selection() else "disabled"; self.modify_button.config(state=new_state); self.delete_button.config(state=new_state)

    def modify_selected_holiday(self):
        selection = self.holidays_tree.selection();
        if not selection: return
        item = self.holidays_tree.item(selection[0]); old_date_str, old_desc, old_type = item['values']
        new_desc = simpledialog.askstring("Modifier la description", "Nouvelle description :", initialvalue=old_desc, parent=self)
        if new_desc is not None and new_desc.strip():
            date_sql = validate_date(old_date_str).strftime("%Y-%m-%d"); self.manager.add_or_update_holiday(date_sql, new_desc.strip(), old_type); self.refresh_holidays_list()

    def delete_selected_holiday(self):
        selection = self.holidays_tree.selection();
        if not selection: return
        item = self.holidays_tree.item(selection[0]); date_display, desc, _ = item['values']; date_sql = validate_date(date_display).strftime("%Y-%m-%d")
        if messagebox.askyesno("Confirmation", f"Êtes-vous sûr de vouloir supprimer :\n{desc} ({date_display}) ?", parent=self):
            if self.manager.delete_holiday(date_sql): self.refresh_holidays_list()
            else: messagebox.showerror("Erreur BD", "La suppression a échoué.", parent=self)

    def restore_auto_holidays(self):
        try: year = int(self.year_var.get())
        except (ValueError, tk.TclError): messagebox.showerror("Année Invalide", "Veuillez sélectionner une année valide.", parent=self); return
        if not messagebox.askyesno("Confirmation", f"Ceci va ajouter ou mettre à jour les jours fériés officiels pour l'année {year}.\nContinuer ?", parent=self): return
        try:
            country_code = CONFIG['conges']['holidays_country']; auto_holidays = holidays.country_holidays(country_code, years=year); count = 0
            for date_obj, name in auto_holidays.items(): self.manager.add_or_update_holiday(date_obj.strftime("%Y-%m-%d"), name, "Automatique"); count += 1
            messagebox.showinfo("Succès", f"{count} jours fériés automatiques restaurés pour {year}.", parent=self); self.refresh_holidays_list()
        except Exception as e: messagebox.showerror("Erreur", f"Une erreur est survenue: {e}", parent=self)

class JustificatifsWindow(tk.Toplevel):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.title("Suivi des Justificatifs Médicaux")
        self.grab_set()
        self.geometry("800x600")
        self.filter_var = tk.StringVar(value="manquant")
        self.search_var = tk.StringVar()
        self._create_widgets()
        self.refresh_list()
        
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True)
        filter_frame = ttk.LabelFrame(main_frame, text="Filtres et Recherche", padding=10); filter_frame.pack(fill="x", pady=(0, 10))
        status_frame = ttk.Frame(filter_frame); status_frame.pack(side="left", fill="x", expand=True)
        ttk.Radiobutton(status_frame, text="Manquants", variable=self.filter_var, value="manquant", command=self.refresh_list).pack(anchor="w")
        ttk.Radiobutton(status_frame, text="Fournis", variable=self.filter_var, value="justifie", command=self.refresh_list).pack(anchor="w")
        ttk.Radiobutton(status_frame, text="Tous", variable=self.filter_var, value="tous", command=self.refresh_list).pack(anchor="w")
        search_frame = ttk.Frame(filter_frame); search_frame.pack(side="left", fill="x", expand=True, padx=(20, 0))
        ttk.Label(search_frame, text="Rechercher un agent (Nom, Prénom, PPR):").pack(anchor="w")
        search_entry_frame = ttk.Frame(search_frame); search_entry_frame.pack(fill="x", pady=5)
        search_entry = ttk.Entry(search_entry_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<Return>", lambda event: self.refresh_list())
        clear_btn = ttk.Button(search_entry_frame, text="X", width=3, command=self._clear_search); clear_btn.pack(side="left", padx=(5, 0))
        ttk.Button(search_frame, text="Rechercher", command=self.refresh_list).pack(anchor="w", pady=5)
        cols = ("Agent", "PPR", "Date Début", "Date Fin", "Jours Pris"); self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", height=10)
        for col in cols: self.tree.heading(col, text=col); self.tree.column(col, width=120)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _clear_search(self):
        self.search_var.set("")
        self.refresh_list()
        
    def refresh_list(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        try:
            filtre_choisi = self.filter_var.get()
            terme_recherche = self.search_var.get().strip()
            conges_list = self.manager.get_sick_leaves_by_status(status=filtre_choisi, search_term=terme_recherche)
            # CORRECTION : Afficher correctement les colonnes du tuple retourné par la DB.
            for row_data in conges_list:
                # row_data = (nom, prenom, ppr, date_debut, date_fin, jours_pris)
                agent_fullname = f"{row_data[0]} {row_data[1]}"
                ppr = row_data[2]
                date_debut = format_date_for_display(row_data[3])
                date_fin = format_date_for_display(row_data[4])
                jours_pris = row_data[5]
                self.tree.insert("", "end", values=(agent_fullname, ppr, date_debut, date_fin, jours_pris))
        except sqlite3.Error as e:
            messagebox.showerror("Erreur BD", f"Impossible de charger la liste : {e}", parent=self)

class ReportWindow(tk.Toplevel):
    def __init__(self, parent, year, inconsistencies):
        super().__init__(parent); self.manager = parent.manager; self.title(f"Rapport d'incohérence pour {year}"); self.grab_set(); self.geometry("900x400")
        main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True)
        info_label = ttk.Label(main_frame, text="Les congés suivants ne sont plus valides car des jours fériés ont été modifiés.\nVous devriez les modifier manuellement.", wraplength=850, justify="center"); info_label.pack(fill="x", pady=10)
        cols = ("Agent", "Début Congé", "Fin Congé", "Jours Pris (Enregistré)", "Jours Dûs (Calculé)"); tree = ttk.Treeview(main_frame, columns=cols, show="headings")
        for col in cols: tree.heading(col, text=col)
        tree.column("Agent", width=200); tree.column("Début Congé", width=120, anchor="center"); tree.column("Fin Congé", width=120, anchor="center"); tree.column("Jours Pris (Enregistré)", width=150, anchor="center"); tree.column("Jours Dûs (Calculé)", width=150, anchor="center")
        tree.tag_configure("error", background="#FFDDDD")
        for conge, recalculated_days in inconsistencies:
            agent = self.manager.get_agent_by_id(conge.agent_id); agent_name = f"{agent.nom} {agent.prenom}" if agent else "Agent Inconnu"
            tree.insert("", "end", values=(agent_name, conge.date_debut.strftime('%d/%m/%Y'), conge.date_fin.strftime('%d/%m/%Y'), conge.jours_pris, recalculated_days), tags=("error",))
        tree.pack(fill="both", expand=True); ttk.Button(main_frame, text="Fermer", command=self.destroy).pack(pady=10)