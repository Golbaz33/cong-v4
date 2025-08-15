# Fichier : ui/widgets/date_picker.py
# Version finale intégrant les améliorations de l'Axe 2.

import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar
from datetime import datetime

# Import des utilitaires nécessaires
from utils.config_loader import CONFIG

class DatePickerWindow(tk.Toplevel):
    """
    Crée une fenêtre TopLevel avec un calendrier pour sélectionner une date.
    Met en évidence les jours fériés pour les types de congés concernés.
    """
    # AXE 2 : Le constructeur attend maintenant 'conge_manager' au lieu de 'db_manager'.
    def __init__(self, parent, entry_field, conge_manager, conge_type=None):
        super().__init__(parent)
        self.entry_field = entry_field
        # AXE 2 : On stocke la référence au manager complet.
        self.manager = conge_manager
        self.conge_type = conge_type
        
        self.title("📅 Sélection de date")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_style()
        self._load_holidays()
        self._create_widgets()
        self._position_window(parent)

    def _setup_style(self):
        """Configure le style des widgets du calendrier."""
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Calendar.TButton', font=('Helvetica', 10), padding=5)

    def _load_holidays(self):
        """Charge les jours fériés si le type de congé le requiert."""
        self.holidays_dict = {}
        types_decompte = CONFIG['conges']['types_decompte_solde']
        
        if self.conge_type in types_decompte:
            year = datetime.now().year
            # AXE 2 : On appelle la méthode du manager pour obtenir les jours fériés.
            # L'interface ne sait plus comment ces jours sont récupérés (DB, API, etc.).
            holidays_set = self.manager.get_holidays_set_for_period(year - 1, year + 1)
            for h_date in holidays_set:
                self.holidays_dict[h_date] = "Jour Férié"

    def _create_widgets(self):
        """Crée et configure le widget Calendrier et les boutons."""
        self.cal = Calendar(
            self,
            selectmode='day',
            date_pattern='dd/mm/yyyy',
            locale='fr_FR',
            font=('Helvetica', 12),
            headersbackground='#4B8BBE',
            normalbackground='#F0F0F0',
            weekendbackground='#FFDDDD',
            selectbackground='#306998'
        )
        self.cal.pack(padx=15, pady=15, fill='both', expand=True)

        # Ajoute les événements pour les jours fériés avec un tag 'holiday'
        for date_obj, name in self.holidays_dict.items():
            self.cal.calevent_create(date_obj, name, "holiday")
        
        # Configure la couleur de fond pour le tag 'holiday'
        self.cal.tag_config("holiday", background='#FFCCCB')

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(0, 10))
        
        ttk.Button(
            btn_frame, 
            text="Valider", 
            style='Calendar.TButton', 
            command=self._on_validate
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text="Annuler", 
            style='Calendar.TButton', 
            command=self.destroy
        ).pack(side=tk.LEFT)

    def _position_window(self, parent):
        """Centre la fenêtre du calendrier par rapport à sa fenêtre parente."""
        self.update_idletasks() # S'assure que les dimensions sont calculées
        
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        self_width = self.winfo_width()
        self_height = self.winfo_height()
        
        x = parent_x + (parent_width // 2) - (self_width // 2)
        y = parent_y + (parent_height // 2) - (self_height // 2)
        
        self.geometry(f"+{x}+{y}")

    def _on_validate(self):
        """
        Met à jour le champ de saisie avec la date sélectionnée, 
        déclenche un événement virtuel et ferme la fenêtre.
        """
        selected_date = self.cal.selection_get()
        if selected_date:
            self.entry_field.delete(0, tk.END)
            self.entry_field.insert(0, selected_date.strftime("%d/%m/%Y"))
            # Déclencher un événement virtuel pour que le formulaire sache qu'une date a été choisie
            self.entry_field.event_generate("<<DatePicked>>")
        self.destroy()