# Fichier : ui/main_window.py
# Version finale avec correction de la définition locale de la fonction.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict, Counter
from dateutil import parser
import logging
import os
import sqlite3
import threading
from datetime import datetime

# Import des composants de votre architecture
from core.conges.manager import CongeManager
from ui.forms.agent_form import AgentForm
from ui.forms.conge_form import CongeForm
from ui.widgets.secondary_windows import HolidaysManagerWindow, JustificatifsWindow
from utils.file_utils import export_agents_to_excel, export_all_conges_to_excel, import_agents_from_excel
# CORRECTION : L'import peut maintenant trouver la fonction dans le fichier d'utilitaires
from utils.date_utils import format_date_for_display, format_date_for_display_short, calculate_reprise_date
from utils.config_loader import CONFIG

# CORRECTION : On supprime la définition locale de la fonction, car elle est maintenant importée.
# def format_date_for_display_short(date_obj): ...

def treeview_sort_column(tv, col, reverse):
    l = [(tv.set(k, col), k) for k in tv.get_children('')]
    numeric_cols = ['Solde', 'Jours', 'PPR']
    try:
        if col in numeric_cols: l.sort(key=lambda t: float(str(t[0]).replace(',', '.')), reverse=reverse)
        else: l.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)
    except (ValueError, IndexError): l.sort(key=lambda t: str(t[0]), reverse=reverse)
    for index, (val, k) in enumerate(l): tv.move(k, '', index)
    tv.heading(col, command=lambda: treeview_sort_column(tv, col, not reverse))


class MainWindow(tk.Tk):
    # ... (le reste du fichier est identique et correct)
    def __init__(self, manager: CongeManager):
        super().__init__()
        self.manager = manager
        self.title(f"{CONFIG['app']['title']} - v{CONFIG['app']['version']}")
        self.minsize(1200, 700)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.current_page = 1
        self.items_per_page = 50
        self.total_pages = 1
        self.create_widgets()
        self.refresh_all()
    def on_close(self):
        if messagebox.askokcancel("Quitter", "Voulez-vous vraiment quitter ?"):
            self.destroy()
    def set_status(self, message):
        self.status_var.set(message)
        self.update_idletasks()
    def create_widgets(self):
        style = ttk.Style(self); style.theme_use('clam')
        style.configure("Treeview", rowheight=25, font=('Helvetica', 10)); style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold')); style.configure("TLabel", font=('Helvetica', 11)); style.configure("TButton", font=('Helvetica', 10)); style.configure("TLabelframe.Label", font=('Helvetica', 12, 'bold'))
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL); main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left_pane = ttk.Frame(main_pane, padding=5); main_pane.add(left_pane, weight=2)
        agents_frame = ttk.LabelFrame(left_pane, text="Agents"); agents_frame.pack(fill=tk.BOTH, expand=True)
        search_frame = ttk.Frame(agents_frame); search_frame.pack(fill=tk.X, padx=5, pady=5); ttk.Label(search_frame, text="Rechercher:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *args: self.search_agents())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var); search_entry.pack(fill=tk.X, expand=True, side=tk.LEFT)
        cols_agents = ("ID", "Nom", "Prénom", "PPR", "Grade", "Solde");
        self.list_agents = ttk.Treeview(agents_frame, columns=cols_agents, show="headings", selectmode="browse")
        for col in cols_agents: self.list_agents.heading(col, text=col, command=lambda c=col: treeview_sort_column(self.list_agents, c, False))
        self.list_agents.column("ID", width=0, stretch=False); self.list_agents.column("Nom", width=120); self.list_agents.column("Prénom", width=120); self.list_agents.column("PPR", width=80, anchor="center"); self.list_agents.column("Grade", width=100); self.list_agents.column("Solde", width=60, anchor="center")
        self.list_agents.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.list_agents.bind("<<TreeviewSelect>>", self.on_agent_select); self.list_agents.bind("<Double-1>", lambda e: self.modify_selected_agent())
        pagination_frame = ttk.Frame(agents_frame); pagination_frame.pack(fill=tk.X, padx=5, pady=5)
        self.prev_button = ttk.Button(pagination_frame, text="<< Précédent", command=self.prev_page); self.prev_button.pack(side=tk.LEFT)
        self.page_label = ttk.Label(pagination_frame, text="Page 1 / 1"); self.page_label.pack(side=tk.LEFT, expand=True)
        self.next_button = ttk.Button(pagination_frame, text="Suivant >>", command=self.next_page); self.next_button.pack(side=tk.RIGHT)
        self.btn_frame_agents = ttk.Frame(agents_frame); self.btn_frame_agents.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(self.btn_frame_agents, text="Ajouter", command=self.add_agent_ui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.btn_frame_agents, text="Modifier", command=self.modify_selected_agent).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.btn_frame_agents, text="Supprimer", command=self.delete_selected_agent).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.io_frame_agents = ttk.Frame(agents_frame); self.io_frame_agents.pack(fill=tk.X, padx=5, pady=(5, 5))
        ttk.Button(self.io_frame_agents, text="Importer Agents (Excel)", command=self.import_agents).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.io_frame_agents, text="Exporter Agents (Excel)", command=self.export_agents).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        right_pane = ttk.PanedWindow(main_pane, orient=tk.VERTICAL); main_pane.add(right_pane, weight=3)
        conges_frame = ttk.LabelFrame(right_pane, text="Congés de l'agent sélectionné"); right_pane.add(conges_frame, weight=3)
        filter_frame = ttk.Frame(conges_frame); filter_frame.pack(fill=tk.X, padx=5, pady=5); ttk.Label(filter_frame, text="Filtrer par type:").pack(side=tk.LEFT, padx=(0, 5))
        self.conge_filter_var = tk.StringVar(value="Tous"); conge_filter_combo = ttk.Combobox(filter_frame, textvariable=self.conge_filter_var, values=["Tous"] + CONFIG['ui']['types_conge'], state="readonly"); conge_filter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True); conge_filter_combo.bind("<<ComboboxSelected>>", self.on_agent_select)
        cols_conges = ("CongeID", "Certificat", "Type", "Début", "Fin", "Date Reprise", "Jours", "Justification", "Intérimaire");
        self.list_conges = ttk.Treeview(conges_frame, columns=cols_conges, show="headings", selectmode="browse")
        for col in cols_conges: self.list_conges.heading(col, text=col, command=lambda c=col: treeview_sort_column(self.list_conges, c, False))
        self.list_conges.column("CongeID", width=0, stretch=False); self.list_conges.column("Certificat", width=80, anchor="center"); self.list_conges.column("Type", width=120); self.list_conges.column("Début", width=90, anchor="center"); self.list_conges.column("Fin", width=90, anchor="center"); self.list_conges.column("Date Reprise", width=90, anchor="center"); self.list_conges.column("Jours", width=50, anchor="center"); self.list_conges.column("Intérimaire", width=150)
        self.list_conges.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.list_conges.tag_configure("summary", background="#e6f2ff", font=("Helvetica", 10, "bold")); self.list_conges.tag_configure("annule", foreground="grey", font=('Helvetica', 10, 'overstrike'))
        self.list_conges.bind("<Double-1>", lambda e: self.on_conge_double_click())
        self.btn_frame_conges = ttk.Frame(conges_frame); self.btn_frame_conges.pack(fill=tk.X, padx=5, pady=(0, 5));
        ttk.Button(self.btn_frame_conges, text="Ajouter", command=self.add_conge_ui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.btn_frame_conges, text="Modifier", command=self.modify_selected_conge).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.btn_frame_conges, text="Supprimer", command=self.delete_selected_conge).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        stats_frame = ttk.LabelFrame(right_pane, text="Tableau de Bord"); right_pane.add(stats_frame, weight=1)
        on_leave_frame = ttk.LabelFrame(stats_frame, text="Agents Actuellement en Congé"); on_leave_frame.pack(fill="x", expand=True, padx=5, pady=5)
        cols_on_leave = ("Agent", "PPR", "Type Congé", "Date Fin"); self.list_on_leave = ttk.Treeview(on_leave_frame, columns=cols_on_leave, show="headings", height=4)
        for col in cols_on_leave: self.list_on_leave.heading(col, text=col)
        self.list_on_leave.column("Agent", width=200); self.list_on_leave.column("PPR", width=100, anchor="center"); self.list_on_leave.column("Type Congé", width=150); self.list_on_leave.column("Date Fin", width=120, anchor="center")
        self.list_on_leave.pack(fill="x", expand=True, padx=5, pady=5)
        summary_stats_frame = ttk.LabelFrame(stats_frame, text="Statistiques Globales"); summary_stats_frame.pack(fill="x", expand=True, padx=5, pady=5)
        self.text_stats = tk.Text(summary_stats_frame, wrap=tk.WORD, font=('Courier New', 10), height=5, relief=tk.FLAT, background=self.cget('bg')); self.text_stats.pack(fill=tk.BOTH, expand=True, padx=10, pady=5); self.text_stats.config(state=tk.DISABLED)
        self.global_actions_frame = ttk.Frame(stats_frame); self.global_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(self.global_actions_frame, text="Actualiser", command=self.refresh_stats).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.global_actions_frame, text="Suivi Justificatifs", command=self.open_justificatifs_suivi).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.global_actions_frame, text="Gérer les Jours Fériés", command=self.open_holidays_manager).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2); ttk.Button(self.global_actions_frame, text="Exporter Tous les Congés", command=self.export_conges).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.status_var = tk.StringVar(value="Prêt."); status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W); status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    def get_selected_agent_id(self):
        selection = self.list_agents.selection(); return int(self.list_agents.item(selection[0])["values"][0]) if selection else None
    def get_selected_conge_id(self):
        selection = self.list_conges.selection();
        if not selection: return None
        item = self.list_conges.item(selection[0]);
        if "summary" in item["tags"]: return None
        return int(item["values"][0]) if item["values"] else None
    def add_agent_ui(self): AgentForm(self, self.manager)
    def modify_selected_agent(self):
        agent_id = self.get_selected_agent_id();
        if agent_id: AgentForm(self, self.manager, agent_id_to_modify=agent_id)
        else: messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un agent à modifier.")
    def delete_selected_agent(self):
        agent_id = self.get_selected_agent_id();
        if not agent_id: messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un agent à supprimer."); return
        agent = self.manager.get_agent_by_id(agent_id);
        if not agent: messagebox.showerror("Erreur", "Agent introuvable."); return
        agent_nom = f"{agent.nom} {agent.prenom}"
        if messagebox.askyesno("Confirmation", f"Supprimer l'agent '{agent_nom}' et tous ses congés ?\nCette action est irréversible."):
            try:
                if self.manager.delete_agent(agent.id): self.set_status(f"Agent '{agent_nom}' supprimé."); self.refresh_all()
            except Exception as e: messagebox.showerror("Erreur de suppression", f"Une erreur est survenue : {e}")
    def add_conge_ui(self):
        agent_id = self.get_selected_agent_id();
        if agent_id: CongeForm(self, self.manager, agent_id)
        else: messagebox.showwarning("Aucun agent", "Veuillez sélectionner un agent.")
    def modify_selected_conge(self):
        agent_id = self.get_selected_agent_id(); conge_id = self.get_selected_conge_id();
        if agent_id and conge_id: CongeForm(self, self.manager, agent_id, conge_id=conge_id)
        else: messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un congé à modifier.")
    def delete_selected_conge(self):
        conge_id = self.get_selected_conge_id(); agent_id = self.get_selected_agent_id();
        if not conge_id: messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un congé à supprimer."); return
        try:
            conge = self.manager.get_conge_by_id(conge_id);
            if not conge: messagebox.showwarning("Erreur", "Le congé n'existe plus."); self.refresh_all(agent_id); return
            msg = "Êtes-vous sûr de vouloir supprimer définitivement ce congé annulé ?" if conge.statut == 'Annulé' else "Êtes-vous sûr de vouloir supprimer ce congé ?\nS'il fait partie d'une division, le congé d'origine sera restauré."
            if messagebox.askyesno("Confirmation", msg):
                if self.manager.delete_conge(conge_id): self.set_status("Congé supprimé."); self.refresh_all(agent_id)
        except (ValueError, sqlite3.Error) as e: messagebox.showerror("Erreur de suppression", str(e))
        except Exception as e: logging.error(f"Erreur inattendue suppression congé: {e}", exc_info=True); messagebox.showerror("Erreur Inattendue", f"Une erreur est survenue: {e}")
    def refresh_all(self, agent_to_select_id=None):
        current_selection = agent_to_select_id or self.get_selected_agent_id(); self.refresh_agents_list(current_selection); self.refresh_stats()
    def refresh_agents_list(self, agent_to_select_id=None):
        for row in self.list_agents.get_children(): self.list_agents.delete(row)
        term = self.search_var.get().strip().lower() or None; total_items = self.manager.get_agents_count(term); self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page); self.current_page = min(self.current_page, self.total_pages); offset = (self.current_page - 1) * self.items_per_page; agents = self.manager.get_all_agents(term=term, limit=self.items_per_page, offset=offset); selected_item_id = None
        for agent in agents:
            item_id = self.list_agents.insert("", "end", values=(agent.id, agent.nom, agent.prenom, agent.ppr, agent.grade, f"{agent.solde:.1f}"))
            if agent.id == agent_to_select_id: selected_item_id = item_id
        if selected_item_id: self.list_agents.selection_set(selected_item_id); self.list_agents.focus(selected_item_id)
        self.on_agent_select(); self.page_label.config(text=f"Page {self.current_page} / {self.total_pages}"); self.prev_button.config(state="normal" if self.current_page > 1 else "disabled"); self.next_button.config(state="normal" if self.current_page < self.total_pages else "disabled"); self.set_status(f"{len(agents)} agents affichés sur {total_items} au total.")
    def refresh_conges_list(self, agent_id):
        self.list_conges.delete(*self.list_conges.get_children()); filtre = self.conge_filter_var.get(); conges_data = self.manager.get_conges_for_agent(agent_id); conges_par_annee = defaultdict(list)
        for c in conges_data:
            if filtre != "Tous" and c.type_conge != filtre: continue
            try: conges_par_annee[c.date_debut.year].append(c)
            except AttributeError: logging.warning(f"Date invalide ou nulle pour congé ID {c.id}")
        for annee in sorted(conges_par_annee.keys(), reverse=True):
            total_jours = sum(c.jours_pris for c in conges_par_annee[annee] if c.type_conge == 'Congé annuel' and c.statut == 'Actif'); summary_id = self.list_conges.insert("", "end", values=("", "", f"📅 ANNÉE {annee}", "", "", "", total_jours, f"{total_jours} jours pris", ""), tags=("summary",), open=True); holidays_set = self.manager.get_holidays_set_for_period(annee, annee + 1)
            for conge in sorted(conges_par_annee[annee], key=lambda c: c.date_debut):
                cert_status = "✅ Justifié" if self.manager.get_certificat_for_conge(conge.id) else "❌ Manquant" if conge.type_conge == 'Congé de maladie' else ""; interim_info = "";
                if conge.interim_id: interim = self.manager.get_agent_by_id(conge.interim_id); interim_info = f"{interim.nom} {interim.prenom}" if interim else "Agent Supprimé"
                tags = ('annule',) if conge.statut == 'Annulé' else (); reprise_date = calculate_reprise_date(conge.date_fin, holidays_set); reprise_date_str = format_date_for_display_short(reprise_date) if reprise_date else ""
                self.list_conges.insert(summary_id, "end", values=(conge.id, cert_status, conge.type_conge, format_date_for_display_short(conge.date_debut), format_date_for_display_short(conge.date_fin), reprise_date_str, conge.jours_pris, conge.justif or "", interim_info), tags=tags)
    def refresh_stats(self):
        for row in self.list_on_leave.get_children(): self.list_on_leave.delete(row)
        try:
            agents_on_leave = self.manager.get_agents_on_leave_today()
            for nom, prenom, ppr, type_conge, date_fin in agents_on_leave: self.list_on_leave.insert("", "end", values=(f"{nom} {prenom}", ppr, type_conge, format_date_for_display(date_fin)))
        except sqlite3.Error as e: self.list_on_leave.insert("", "end", values=(f"Erreur DB: {e}", "", "", ""))
        self.text_stats.config(state=tk.NORMAL); self.text_stats.delete("1.0", tk.END)
        try:
            all_conges = self.manager.get_all_conges(); nb_agents = self.manager.get_agents_count(); active_conges = [c for c in all_conges if c.statut == 'Actif']; total_jours_pris = sum(c.jours_pris for c in active_conges)
            self.text_stats.insert(tk.END, f"{'Nombre total d\'agents':<25}: {nb_agents}\n"); self.text_stats.insert(tk.END, f"{'Total des jours de congés actifs':<25}: {total_jours_pris}\n\n"); self.text_stats.insert(tk.END, "Répartition par type de congé (actifs):\n")
            if active_conges:
                for type_conge, count in Counter(c.type_conge for c in active_conges).most_common(): self.text_stats.insert(tk.END, f"  - {type_conge:<22}: {count} ({(count / len(active_conges)) * 100:.1f}%)\n")
        except sqlite3.Error as e: self.text_stats.insert(tk.END, f"Erreur de lecture des statistiques: {e}")
        finally: self.text_stats.config(state=tk.DISABLED)
    def search_agents(self): self.current_page = 1; self.refresh_agents_list()
    def on_agent_select(self, event=None):
        if self.get_selected_agent_id(): self.refresh_conges_list(self.get_selected_agent_id())
        else: self.list_conges.delete(*self.list_conges.get_children())
    def prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self.refresh_agents_list(self.get_selected_agent_id())
    def next_page(self):
        if self.current_page < self.total_pages: self.current_page += 1; self.refresh_agents_list(self.get_selected_agent_id())
    def on_conge_double_click(self):
        conge_id = self.get_selected_conge_id();
        if not conge_id: return
        conge_type = self.list_conges.item(self.list_conges.selection()[0])["values"][2]
        if conge_type == "Congé de maladie":
            cert = self.manager.get_certificat_for_conge(conge_id)
            if cert and cert[4] and os.path.exists(cert[4]):
                try: os.startfile(os.path.realpath(cert[4]))
                except Exception as e: messagebox.showerror("Erreur d'ouverture", f"Impossible d'ouvrir le fichier:\n{e}", parent=self)
            else: messagebox.showinfo("Justificatif", "Aucun justificatif n'est attaché à ce congé.", parent=self)
        else: self.modify_selected_conge()
    def open_holidays_manager(self): HolidaysManagerWindow(self, self.manager)
    def open_justificatifs_suivi(self): JustificatifsWindow(self, self.manager)
    def export_agents(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Fichiers Excel", "*.xlsx")], title="Exporter la liste des agents", initialfile=f"Export_Agents_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
        if not save_path: return
        db_path = self.manager.db.db_file
        self._run_long_task(lambda: export_agents_to_excel(db_path, save_path), self._on_task_complete, "Exportation des agents en cours...")
    def export_conges(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Fichiers Excel", "*.xlsx")], title="Exporter tous les congés", initialfile=f"Export_Conges_Total_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
        if not save_path: return
        db_path = self.manager.db.db_file
        self._run_long_task(lambda: export_all_conges_to_excel(db_path, save_path), self._on_task_complete, "Exportation de tous les congés en cours...")
    def import_agents(self):
        source_path = filedialog.askopenfilename(title="Sélectionner un fichier Excel à importer", filetypes=[("Fichiers Excel", "*.xlsx")])
        if not source_path: return
        db_path = self.manager.db.db_file
        self._run_long_task(lambda: import_agents_from_excel(db_path, source_path), self._on_import_complete, "Importation des agents depuis Excel en cours...")
    def _run_long_task(self, task_lambda, on_complete, status_message):
        self.set_status(status_message); self.config(cursor="watch"); self._toggle_buttons_state("disabled"); result_container = []
        def task_wrapper():
            try: result_container.append(task_lambda())
            except Exception as e: result_container.append(e)
        worker_thread = threading.Thread(target=task_wrapper); worker_thread.start(); self._check_thread_completion(worker_thread, result_container, on_complete)
    def _check_thread_completion(self, thread, result_container, on_complete):
        if thread.is_alive(): self.after(100, lambda: self._check_thread_completion(thread, result_container, on_complete))
        else:
            result = result_container[0] if result_container else None; on_complete(result); self.config(cursor=""); self._toggle_buttons_state("normal"); self.set_status("Prêt.")
    def _on_task_complete(self, result):
        if isinstance(result, Exception): messagebox.showerror("Erreur", f"L'opération a échoué:\n{result}")
        elif result: messagebox.showinfo("Succès", result)
    
    def _on_import_complete(self, result):
        self._on_task_complete(result)
        if not isinstance(result, Exception): self.refresh_all()
    def _toggle_buttons_state(self, state):
        for frame in [self.btn_frame_agents, self.io_frame_agents, self.btn_frame_conges, self.global_actions_frame]:
            for child in frame.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Combobox)):
                    child.config(state=state)