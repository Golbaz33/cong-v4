# Fichier : ui/widgets/secondary_windows.py
# Version finale avec simplification du texte pour la suppression des jours fériés.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import holidays
import sqlite3
import threading
import os
import shutil

from ui.widgets.date_picker import DatePickerWindow
from utils.date_utils import validate_date, format_date_for_display
from utils.config_loader import CONFIG

class EditHolidayWindow(tk.Toplevel):
    """
    Fenêtre de formulaire pour modifier la date et le nom d'un jour férié.
    """
    def __init__(self, parent, original_date, original_name, callback):
        super().__init__(parent)
        self.original_date_str = original_date
        self.callback = callback

        self.title("Modifier le Jour Férié")
        self.grab_set()
        self.resizable(False, False)
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Date:").grid(row=0, column=0, sticky="w", pady=5)
        self.date_entry = ttk.Entry(frame, width=25)
        self.date_entry.insert(0, original_date)
        self.date_entry.grid(row=0, column=1, padx=5)

        ttk.Label(frame, text="Nom/Description:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_entry = ttk.Entry(frame, width=25)
        self.name_entry.insert(0, original_name)
        self.name_entry.grid(row=1, column=1, padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Valider", command=self._on_validate).pack(side="right")
        ttk.Button(btn_frame, text="Annuler", command=self.destroy).pack(side="right", padx=10)
        
        self.transient(parent)
        self.geometry(f"+{parent.winfo_rootx()+50}+{parent.winfo_rooty()+50}")
        self.focus_set()
        self.wait_window()

    def _on_validate(self):
        new_date_str = self.date_entry.get().strip()
        new_name = self.name_entry.get().strip()

        new_date_obj = validate_date(new_date_str)

        if not new_date_obj or not new_name:
            messagebox.showerror("Erreur de saisie", "Veuillez entrer une date valide et un nom.", parent=self)
            return
        
        self.callback(self.original_date_str, new_date_obj, new_name)
        self.destroy()

class BackupWindow(tk.Toplevel):
    """
    Fenêtre de gestion des sauvegardes et de la restauration.
    """
    def __init__(self, parent, manager, main_app_instance):
        super().__init__(parent)
        self.manager = manager
        self.main_app = main_app_instance
        self.db_path = self.manager.db.get_db_path()
        self.base_dir = os.path.dirname(self.db_path)
        self.backups_dir = os.path.join(self.base_dir, "backups")

        self.title("Gérer les Sauvegardes et Restaurer")
        self.geometry("700x400")
        self.grab_set()
        self.transient(parent)

        self._create_widgets()
        self._populate_backups()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        list_frame = ttk.LabelFrame(main_frame, text="Sauvegardes Disponibles", padding=10)
        list_frame.pack(fill="both", expand=True)
        
        cols = ("Fichier", "Date de création", "Taille")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings")
        self.tree.heading("Fichier", text="Nom du Fichier")
        self.tree.heading("Date de création", text="Date de création")
        self.tree.heading("Taille", text="Taille")
        self.tree.column("Fichier", width=350)
        self.tree.column("Date de création", width=150, anchor="center")
        self.tree.column("Taille", width=100, anchor="e")
        self.tree.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(main_frame, padding=(0, 10))
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Fermer", command=self.destroy).pack(side="right")
        ttk.Button(btn_frame, text="Restaurer la version sélectionnée", command=self._run_restore).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Supprimer la sauvegarde", command=self._delete_backup).pack(side="left")

    def _populate_backups(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        if not os.path.exists(self.backups_dir):
            return

        backups = []
        for filename in os.listdir(self.backups_dir):
            if filename.endswith((".db", ".sqlite3")):
                full_path = os.path.join(self.backups_dir, filename)
                try:
                    mtime = os.path.getmtime(full_path)
                    size = os.path.getsize(full_path)
                    backups.append((filename, mtime, size))
                except OSError:
                    continue
        
        backups.sort(key=lambda x: x[1], reverse=True)
        
        for filename, mtime, size in backups:
            date_str = datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M:%S')
            size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB"
            self.tree.insert("", "end", values=(filename, date_str, size_str))

    def _get_selected_backup_path(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner une sauvegarde dans la liste.", parent=self)
            return None
        
        filename = self.tree.item(selection[0], "values")[0]
        return os.path.join(self.backups_dir, filename)

    def _delete_backup(self):
        backup_path = self._get_selected_backup_path()
        if not backup_path:
            return

        if messagebox.askyesno("Confirmation", f"Êtes-vous sûr de vouloir supprimer définitivement le fichier de sauvegarde suivant ?\n\n{os.path.basename(backup_path)}", parent=self):
            try:
                os.remove(backup_path)
                messagebox.showinfo("Succès", "La sauvegarde a été supprimée.", parent=self)
                self._populate_backups()
            except OSError as e:
                messagebox.showerror("Erreur", f"Impossible de supprimer le fichier : {e}", parent=self)
    
    def _run_restore(self):
        backup_path = self._get_selected_backup_path()
        if not backup_path:
            return
        
        msg = ("Êtes-vous absolument certain de vouloir restaurer cette version ?\n\n"
               "ATTENTION : Toutes les données actuelles seront PERDUES et remplacées par les données de la sauvegarde. "
               "Cette action est IRRÉVERSIBLE.")
        
        if messagebox.askyesno("Confirmation de Restauration", msg, icon='warning', parent=self):
            try:
                self.manager.db.close()
                shutil.copy2(backup_path, self.db_path)
                messagebox.showinfo("Restauration Réussie", "La restauration a été effectuée avec succès.\n\nL'application va maintenant redémarrer pour appliquer les changements.", parent=self)
                self.main_app.trigger_restart()
            except Exception as e:
                messagebox.showerror("Erreur Critique", f"La restauration a échoué : {e}\n\nL'application risque d'être instable. Veuillez la redémarrer.", parent=self)
                self.destroy()

class AdminWindow(tk.Toplevel):
    def __init__(self, parent, conge_manager):
        super().__init__(parent)
        self.parent_window = parent
        self.manager = conge_manager
        
        self.title("Administration")
        self.grab_set()
        self.geometry("800x600")

        self.annee_exercice = self.manager.get_annee_exercice()
        self.selected_agent_id = tk.StringVar()
        self.solde_entries = {}

        self._create_widgets()
        
    def _create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_gestion = ttk.Frame(notebook)
        tab_soldes = ttk.Frame(notebook)
        tab_feries = ttk.Frame(notebook)
        
        notebook.add(tab_gestion, text=" Gestion Annuelle ")
        notebook.add(tab_soldes, text=" Gestion Manuelle des Soldes ")
        notebook.add(tab_feries, text=" Jours Fériés ")
        
        self._populate_gestion_tab(tab_gestion)
        self._populate_soldes_tab(tab_soldes)
        self._populate_feries_tab(tab_feries)

    def _populate_soldes_tab(self, parent_frame):
        selection_frame = ttk.LabelFrame(parent_frame, text="Sélectionner un Agent", padding=10)
        selection_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(selection_frame, text="Agent :").pack(side="left", padx=(0, 5))
        
        all_agents = self.manager.get_all_agents()
        agent_names = sorted([f"{agent.nom} {agent.prenom} (PPR: {agent.ppr})" for agent in all_agents])
        self.agent_map = {f"{agent.nom} {agent.prenom} (PPR: {agent.ppr})": agent.id for agent in all_agents}

        agent_combo = ttk.Combobox(selection_frame, textvariable=self.selected_agent_id, values=agent_names, state="readonly", width=50)
        agent_combo.pack(side="left", fill="x", expand=True)
        agent_combo.bind("<<ComboboxSelected>>", self._on_agent_selected_for_soldes)

        self.soldes_display_frame = ttk.LabelFrame(parent_frame, text="Soldes de l'Agent Sélectionné", padding=10)
        self.soldes_display_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(self.soldes_display_frame)
        scrollbar = ttk.Scrollbar(self.soldes_display_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        save_button = ttk.Button(parent_frame, text="Enregistrer les Modifications de Solde", command=self._save_soldes_manuellement)
        save_button.pack(pady=10)

    def _on_agent_selected_for_soldes(self, event=None):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.solde_entries.clear()
        agent_name = self.selected_agent_id.get()
        if not agent_name: return
            
        agent_id = self.agent_map[agent_name]
        agent = self.manager.get_agent_by_id(agent_id)
        
        sorted_soldes = sorted(agent.soldes_annuels, key=lambda s: s.annee, reverse=True)

        for i, solde_annuel in enumerate(sorted_soldes):
            label_text = f"Année {solde_annuel.annee} ({solde_annuel.statut}) :"
            ttk.Label(self.scrollable_frame, text=label_text).grid(row=i, column=0, sticky="w", padx=5, pady=4)
            entry = ttk.Entry(self.scrollable_frame, width=10)
            entry.grid(row=i, column=1, padx=5)
            entry.insert(0, f"{solde_annuel.solde:.1f}")
            self.solde_entries[solde_annuel.id] = entry

    def _save_soldes_manuellement(self):
        agent_name = self.selected_agent_id.get()
        if not agent_name:
            messagebox.showwarning("Aucun Agent", "Veuillez d'abord sélectionner un agent.", parent=self)
            return

        updated_soldes = {}
        try:
            for solde_id, entry in self.solde_entries.items():
                new_value = float(entry.get().replace(",", "."))
                if new_value < 0:
                    raise ValueError("Les soldes ne peuvent pas être négatifs.")
                updated_soldes[solde_id] = new_value
        except ValueError as e:
            messagebox.showerror("Erreur de Saisie", f"Veuillez entrer des nombres valides pour les soldes.\n{e}", parent=self)
            return
        
        try:
            if self.manager.update_soldes_manuellement(updated_soldes):
                messagebox.showinfo("Succès", "Les soldes ont été mis à jour.", parent=self)
                self.parent_window.refresh_all()
                self._on_agent_selected_for_soldes()
        except Exception as e:
             messagebox.showerror("Erreur", f"La mise à jour a échoué : {e}", parent=self)

    def _populate_gestion_tab(self, parent_frame):
        main_pane = ttk.PanedWindow(parent_frame, orient=tk.VERTICAL); main_pane.pack(fill="both", expand=True, pady=5)
        glissement_frame = ttk.LabelFrame(main_pane, text="Clôture de l'Exercice Annuel", padding=10)
        main_pane.add(glissement_frame, weight=1)
        glissement_label = ttk.Label(glissement_frame, text=f"L'exercice actuel est {self.annee_exercice}. La clôture mettra à jour l'application pour l'exercice {self.annee_exercice + 1}.\nLe solde de l'année {self.annee_exercice - 2} passera au statut 'Expiré'.", wraplength=700)
        glissement_label.pack(pady=5, fill="x")
        glissement_btn = ttk.Button(glissement_frame, text=f"Clôturer l'exercice {self.annee_exercice}", command=self._run_glissement_annuel)
        glissement_btn.pack(pady=10)
        backup_btn = ttk.Button(glissement_frame, text="Gérer les Sauvegardes / Restaurer", command=self._open_backup_window)
        backup_btn.pack(pady=5)
        apurement_frame = ttk.LabelFrame(main_pane, text="Apurement des Soldes Expirés", padding=10)
        main_pane.add(apurement_frame, weight=3)
        cols = ("id", "Agent", "Année du Solde", "Jours Expirés"); self.tree_expires = ttk.Treeview(apurement_frame, columns=cols, show="headings", selectmode="extended"); self.tree_expires.heading("Agent", text="Agent"); self.tree_expires.heading("Année du Solde", text="Année du Solde"); self.tree_expires.heading("Jours Expirés", text="Jours Expirés"); self.tree_expires.column("id", width=0, stretch=False); self.tree_expires.column("Année du Solde", anchor="center", width=120); self.tree_expires.column("Jours Expirés", anchor="center", width=120); self.tree_expires.pack(fill="both", expand=True, pady=5)
        apurement_btn = ttk.Button(apurement_frame, text="Apurer les soldes sélectionnés (mettre à 0)", command=self._run_apurement)
        apurement_btn.pack(pady=5)
        self.refresh_soldes_expires_list()

    def _open_backup_window(self):
        BackupWindow(self, self.manager, self.parent_window)

    def _populate_feries_tab(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, padding=10); main_frame.pack(fill="both", expand=True); top_frame = ttk.LabelFrame(main_frame, text="Jours Fériés Enregistrés"); top_frame.pack(fill="x", pady=5, padx=5); year_frame = ttk.Frame(top_frame, padding=5); year_frame.pack(fill="x"); ttk.Label(year_frame, text="Année:").pack(side="left"); current_year = datetime.now().year; self.year_var = tk.StringVar(value=str(current_year)); self.year_spinbox = ttk.Spinbox(year_frame, from_=current_year - 5, to=current_year + 5, textvariable=self.year_var, width=8, command=self.refresh_holidays_list); self.year_spinbox.pack(side="left", padx=5); cols = ("Date", "Description", "Type"); self.holidays_tree = ttk.Treeview(top_frame, columns=cols, show="headings", height=10);
        for col in cols: self.holidays_tree.heading(col, text=col)
        self.holidays_tree.column("Date", width=100, anchor="center"); self.holidays_tree.column("Description", width=250); self.holidays_tree.column("Type", width=100, anchor="center"); self.holidays_tree.pack(fill="both", expand=True, padx=5, pady=5);
        action_frame = ttk.Frame(top_frame); action_frame.pack(pady=5, fill="x", padx=5)
        # --- CORRECTION DU TEXTE DU BOUTON ---
        delete_btn = ttk.Button(action_frame, text="Supprimer le jour sélectionné", command=self._delete_holiday); delete_btn.pack(side="right")
        edit_btn = ttk.Button(action_frame, text="Modifier le jour sélectionné", command=self._edit_holiday); edit_btn.pack(side="right", padx=(0, 10))
        bottom_frame = ttk.LabelFrame(main_frame, text="Ajouter un Jour Férié Personnalisé"); bottom_frame.pack(fill="x", pady=5, padx=5); add_frame = ttk.Frame(bottom_frame, padding=5); add_frame.pack(); ttk.Label(add_frame, text="Date:").grid(row=0, column=0, sticky="w", pady=2); self.date_entry = ttk.Entry(add_frame, width=15); self.date_entry.grid(row=0, column=1, padx=5); ttk.Button(add_frame, text="📅", width=2, command=lambda: DatePickerWindow(self, self.date_entry, self.manager)).grid(row=0, column=2); ttk.Label(add_frame, text="Description:").grid(row=1, column=0, sticky="w", pady=2); self.desc_entry = ttk.Entry(add_frame, width=30); self.desc_entry.grid(row=1, column=1, columnspan=2, padx=5); ttk.Button(bottom_frame, text="Ajouter ce jour férié", command=self.add_holiday).pack(pady=5); self.refresh_holidays_list()

    def refresh_soldes_expires_list(self):
        for row in self.tree_expires.get_children(): self.tree_expires.delete(row)
        try:
            soldes_expires = self.manager.get_soldes_expires()
            for solde_id, nom, prenom, annee, solde in soldes_expires:
                agent_name = f"{nom} {prenom}"; self.tree_expires.insert("", "end", values=(solde_id, agent_name, annee, f"{solde:.1f} j"))
        except Exception as e: messagebox.showerror("Erreur", f"Impossible de charger les soldes expirés : {e}", parent=self)

    def _run_glissement_annuel(self):
        if messagebox.askyesno("Confirmation", f"Êtes-vous sûr de vouloir clôturer l'exercice {self.annee_exercice} ?\nCette action est IRREVERSIBLE.", icon='warning', parent=self):
            try:
                db_path = self.manager.db.get_db_path()
                base_dir = os.path.dirname(db_path)
                backups_dir = os.path.join(base_dir, "backups")
                os.makedirs(backups_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                db_filename = os.path.basename(db_path)
                backup_filename = f"backup_{timestamp}_AVANT_CLOTURE_{self.annee_exercice}_{db_filename}"
                backup_path = os.path.join(backups_dir, backup_filename)
                shutil.copy2(db_path, backup_path)
            except Exception as e:
                messagebox.showerror("Échec de la Sauvegarde", f"La sauvegarde automatique a échoué. L'opération de clôture est annulée.\n\nErreur : {e}", parent=self)
                return
            try:
                self.manager.effectuer_glissement_annuel()
                messagebox.showinfo("Succès", f"Le glissement annuel a été effectué.\nUne sauvegarde a été créée ici :\n{backup_path}", parent=self)
                self.parent_window.refresh_all()
                self.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Le glissement annuel a échoué : {e}\n\nPensez à vérifier la sauvegarde créée avant de réessayer.", parent=self)

    def _run_apurement(self):
        selection = self.tree_expires.selection()
        if not selection: messagebox.showwarning("Aucune sélection", "Veuillez sélectionner les soldes à apurer.", parent=self); return
        solde_ids = [self.tree_expires.item(item, "values")[0] for item in selection]
        if messagebox.askyesno("Confirmation", f"Mettre à zéro les {len(solde_ids)} soldes expirés sélectionnés ?\nCette action est irréversible.", parent=self):
            try: self.manager.apurer_soldes(solde_ids); self.refresh_soldes_expires_list()
            except Exception as e: messagebox.showerror("Erreur", f"L'apurement a échoué : {e}", parent=self)

    def refresh_holidays_list(self):
        for row in self.holidays_tree.get_children(): self.holidays_tree.delete(row)
        try:
            year = int(self.year_var.get())
            country_code = CONFIG['conges']['holidays_country']
            official_holidays = holidays.country_holidays(country_code, years=year)
            custom_holidays_list = self.manager.get_holidays_for_year(str(year))
            all_holidays_dict = {}
            for h_date, h_name in official_holidays.items(): all_holidays_dict[h_date] = (h_name, "Officiel")
            for h_date_str, h_name, h_type in custom_holidays_list: all_holidays_dict[validate_date(h_date_str).date()] = (h_name, h_type)
            for h_date, (h_name, h_type) in sorted(all_holidays_dict.items()): self.holidays_tree.insert("", "end", values=(format_date_for_display(h_date), h_name, h_type))
        except (tk.TclError, ValueError): pass
        except Exception as e: messagebox.showerror("Erreur", f"Impossible de charger les jours fériés: {e}", parent=self)

    def _get_selected_holiday_info(self):
        selection = self.holidays_tree.selection()
        if not selection:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un jour férié dans la liste.", parent=self)
            return None, None
        item = self.holidays_tree.item(selection[0])
        return item['values'][0], item['values'][1]

    def _delete_holiday(self):
        date_str, desc = self._get_selected_holiday_info()
        if not date_str: return
        date_sql = validate_date(date_str).strftime('%Y-%m-%d')
        # --- CORRECTION DU MESSAGE DE CONFIRMATION ---
        msg = f"Voulez-vous vraiment supprimer l'entrée personnalisée pour le jour férié :\n\n{desc} ({date_str}) ?"
        if messagebox.askyesno("Confirmation de Suppression", msg, parent=self):
            try:
                if self.manager.delete_holiday(date_sql):
                    self.refresh_holidays_list()
                else:
                    messagebox.showerror("Échec", "La suppression a échoué.", parent=self)
            except Exception as e:
                messagebox.showerror("Erreur", f"Une erreur est survenue : {e}", parent=self)

    def _edit_holiday(self):
        original_date_str, original_name = self._get_selected_holiday_info()
        if not original_date_str:
            return
        EditHolidayWindow(self, original_date_str, original_name, self._process_holiday_update)

    def _process_holiday_update(self, original_date_str, new_date_obj, new_name):
        try:
            original_date_sql = validate_date(original_date_str).strftime('%Y-%m-%d')
            new_date_sql = new_date_obj.strftime('%Y-%m-%d')
            if original_date_sql != new_date_sql:
                self.manager.delete_holiday(original_date_sql)
            if self.manager.add_or_update_holiday(new_date_sql, new_name, "Personnalisé"):
                self.refresh_holidays_list()
            else:
                messagebox.showerror("Échec", "La mise à jour a échoué.", parent=self)
        except Exception as e:
            messagebox.showerror("Erreur", f"Une erreur est survenue lors de la mise à jour : {e}", parent=self)

    def add_holiday(self):
        date_str = self.date_entry.get(); desc = self.desc_entry.get().strip(); validated_date = validate_date(date_str)
        if not validated_date or not desc: messagebox.showerror("Erreur", "Veuillez entrer une date et une description valides.", parent=self); return
        date_sql = validated_date.strftime("%Y-%m-%d")
        if self.manager.add_holiday(date_sql, desc, "Personnalisé"): self.desc_entry.delete(0, tk.END); self.date_entry.delete(0, tk.END); self.refresh_holidays_list()
        else: messagebox.showerror("Erreur", "Cette date est déjà enregistrée.", parent=self)

class JustificatifsWindow(tk.Toplevel):
    def __init__(self, parent, manager):
        super().__init__(parent); self.manager = manager; self.title("Suivi des Justificatifs Médicaux"); self.grab_set(); self.geometry("800x600"); self.filter_var = tk.StringVar(value="manquant"); self.search_var = tk.StringVar(); self._create_widgets(); self.refresh_list()
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True); filter_frame = ttk.LabelFrame(main_frame, text="Filtres et Recherche", padding=10); filter_frame.pack(fill="x", pady=(0, 10)); status_frame = ttk.Frame(filter_frame); status_frame.pack(side="left", fill="x", expand=True); ttk.Radiobutton(status_frame, text="Manquants", variable=self.filter_var, value="manquant", command=self.refresh_list).pack(anchor="w"); ttk.Radiobutton(status_frame, text="Fournis", variable=self.filter_var, value="justifie", command=self.refresh_list).pack(anchor="w"); ttk.Radiobutton(status_frame, text="Tous", variable=self.filter_var, value="tous", command=self.refresh_list).pack(anchor="w"); search_frame = ttk.Frame(filter_frame); search_frame.pack(side="left", fill="x", expand=True, padx=(20, 0)); ttk.Label(search_frame, text="Rechercher un agent (Nom, Prénom, PPR):").pack(anchor="w"); search_entry_frame = ttk.Frame(search_frame); search_entry_frame.pack(fill="x", pady=5); search_entry = ttk.Entry(search_entry_frame, textvariable=self.search_var, width=30); search_entry.pack(side="left", fill="x", expand=True); search_entry.bind("<Return>", lambda event: self.refresh_list()); clear_btn = ttk.Button(search_entry_frame, text="X", width=3, command=self._clear_search); clear_btn.pack(side="left", padx=(5, 0)); ttk.Button(search_frame, text="Rechercher", command=self.refresh_list).pack(anchor="w", pady=5); cols = ("Agent", "PPR", "Date Début", "Date Fin", "Jours Pris"); self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", height=10);
        for col in cols: self.tree.heading(col, text=col); self.tree.column(col, width=120)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
    def _clear_search(self): self.search_var.set(""); self.refresh_list()
    def refresh_list(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        try:
            filtre_choisi = self.filter_var.get(); terme_recherche = self.search_var.get().strip(); conges_list = self.manager.get_sick_leaves_by_status(status=filtre_choisi, search_term=terme_recherche)
            for row_data in conges_list:
                agent_fullname = f"{row_data[0]} {row_data[1]}"; ppr = row_data[2]; date_debut = format_date_for_display(row_data[3]); date_fin = format_date_for_display(row_data[4]); jours_pris = row_data[5]
                self.tree.insert("", "end", values=(agent_fullname, ppr, date_debut, date_fin, jours_pris))
        except sqlite3.Error as e: messagebox.showerror("Erreur BD", f"Impossible de charger la liste : {e}", parent=self)

class ReportWindow(tk.Toplevel):
    def __init__(self, parent, year, inconsistencies):
        super().__init__(parent); self.manager = parent.manager; self.title(f"Rapport d'incohérence pour {year}"); self.grab_set(); self.geometry("900x400"); main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True); info_label = ttk.Label(main_frame, text="Les congés suivants ne sont plus valides car des jours fériés ont été modifiés.\nVous devriez les modifier manuellement.", wraplength=850, justify="center"); info_label.pack(fill="x", pady=10); cols = ("Agent", "Début Congé", "Fin Congé", "Jours Pris (Enregistré)", "Jours Dûs (Calculé)"); tree = ttk.Treeview(main_frame, columns=cols, show="headings");
        for col in cols: tree.heading(col, text=col)
        tree.column("Agent", width=200); tree.column("Début Congé", width=120, anchor="center"); tree.column("Fin Congé", width=120, anchor="center"); tree.column("Jours Pris (Enregistré)", width=150, anchor="center"); tree.column("Jours Dûs (Calculé)", width=150, anchor="center"); tree.tag_configure("error", background="#FFDDDD")
        for conge, recalculated_days in inconsistencies:
            agent = self.manager.get_agent_by_id(conge.agent_id); agent_name = f"{agent.nom} {agent.prenom}" if agent else "Agent Inconnu"
            tree.insert("", "end", values=(agent_name, conge.date_debut.strftime('%d/%m/%Y'), conge.date_fin.strftime('%d/%m/%Y'), conge.jours_pris, recalculated_days), tags=("error",))
        tree.pack(fill="both", expand=True); ttk.Button(main_frame, text="Fermer", command=self.destroy).pack(pady=10)