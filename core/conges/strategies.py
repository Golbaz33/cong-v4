# Fichier : core/conges/strategies.py
# Version finale : gère le calcul des durées et la configuration de l'UI.

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import os

from utils.date_utils import jours_ouvres
from utils.config_loader import CONFIG

class CongeStrategy(ABC):
    """Interface de base pour toutes les stratégies de congés."""
    def __init__(self):
        self.days_value = "1"
        self.days_state = "normal"
        self.end_date_state = "normal"
        self.requires_certificat = False

    def configure_ui(self, form):
        """Configure les widgets du formulaire de congé."""
        form.days_var.set(self.days_value)
        form.days_spinbox.config(state=self.days_state)
        form.end_date_entry.config(state=self.end_date_state)

        if self.requires_certificat:
            self._setup_certificat(form)
        else:
            form.cert_frame.pack_forget()

    def _setup_certificat(self, form):
        """Affiche et configure la section du certificat médical."""
        form.cert_frame.pack(fill="x", pady=10)
        if form.is_modification:
            cert = form.manager.get_certificat_for_conge(form.conge_id)
            if cert and cert[4]: # cert[4] is the file path
                form.original_cert_path = cert[4]
                form.cert_path_var.set(cert[4])
        self._update_certificat_display(form)

    def _update_certificat_display(self, form):
        """Met à jour l'affichage du nom de fichier du certificat."""
        path = form.cert_path_var.get()
        if path and os.path.exists(path):
            form.cert_file_label.config(text=f"Fichier : {os.path.basename(path)}")
            form.remove_cert_btn.config(state="normal")
        else:
            form.cert_file_label.config(text="Aucun fichier attaché.")
            form.remove_cert_btn.config(state="disabled")

    @abstractmethod
    def calculate_end_date(self, start_date, days_to_add, holidays_set):
        pass

    @abstractmethod
    def calculate_days(self, start_date, end_date, holidays_set):
        pass

# --- Implémentations concrètes ---

class CongeAnnuelStrategy(CongeStrategy):
    """Stratégie pour les congés annuels, calculés en jours ouvrés."""
    def calculate_end_date(self, start_date, days_to_add, holidays_set):
        # La seule différence est la suppression des .date() inutiles
        if days_to_add <= 0: return start_date 
        temp_date = start_date
        days_counted = 0
        while days_counted < days_to_add:
            if temp_date.weekday() < 5 and temp_date not in holidays_set:
                days_counted += 1
            if days_counted < days_to_add:
                temp_date += timedelta(days=1)
        return temp_date

    def calculate_days(self, start_date, end_date, holidays_set):
        return jours_ouvres(start_date, end_date, holidays_set)

class CongeCalendaireStrategy(CongeStrategy):
    """Stratégie pour les congés calculés en jours calendaires."""
    def calculate_end_date(self, start_date, days_to_add, holidays_set):
        if days_to_add <= 0: return start_date
        return start_date + timedelta(days=days_to_add - 1)

    def calculate_days(self, start_date, end_date, holidays_set):
        return (end_date - start_date).days + 1

class CongeMaladieStrategy(CongeCalendaireStrategy):
    """Stratégie pour le congé maladie, avec certificat requis."""
    def __init__(self):
        super().__init__()
        self.requires_certificat = True

class CongeMaterniteStrategy(CongeCalendaireStrategy):
    """Stratégie pour le congé maternité, avec une durée fixe."""
    def __init__(self):
        super().__init__()
        self.days_value = str(CONFIG['conges']['maternite_duree'])
        self.days_state = "normal"
        self.end_date_state = "normal"

class CongePaterniteStrategy(CongeCalendaireStrategy):
    """Stratégie pour le congé paternité, avec une durée fixe."""
    def __init__(self):
        super().__init__()
        self.days_value = str(CONFIG['conges']['paternite_duree'])
        self.days_state = "normal"
        self.end_date_state = "normal"