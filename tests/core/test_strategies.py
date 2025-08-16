import sys
import os
from datetime import date

# --- Configuration pour permettre l'importation depuis le dossier racine ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
# ---------------------------------------------------------------------------

import pytest
from core.conges.strategies import CongeAnnuelStrategy, CongeCalendaireStrategy
from utils.config_loader import CONFIG, load_config

# Charger une configuration minimale pour les tests
# Créez un fichier 'config.yaml' à la racine si ce n'est pas déjà fait.
if not CONFIG:
    # Simule une structure de config minimale
    mock_config = {
        'app': {'title': 'Test', 'version': '1.0'},
        'conges': {'maternite_duree': 98, 'paternite_duree': 21, 'types_decompte_solde': ['Congé annuel']}
    }
    CONFIG.update(mock_config)


# --- Données de test réutilisables ---
HOLIDAYS_SET_FIXTURE = {
    date(2024, 8, 19),  # Un lundi
    date(2024, 8, 24),  # Un samedi
}

# --- Tests pour la CongeAnnuelStrategy (jours ouvrés) ---

def test_annuel_calculate_days_simple():
    strategy = CongeAnnuelStrategy()
    start_date = date(2024, 8, 5)  # Lundi
    end_date = date(2024, 8, 9)    # Vendredi
    assert strategy.calculate_days(start_date, end_date, HOLIDAYS_SET_FIXTURE) == 5

def test_annuel_calculate_days_across_weekend():
    strategy = CongeAnnuelStrategy()
    start_date = date(2024, 8, 9)   # Vendredi
    end_date = date(2024, 8, 12)  # Lundi suivant
    assert strategy.calculate_days(start_date, end_date, HOLIDAYS_SET_FIXTURE) == 2

def test_annuel_calculate_days_with_holiday():
    strategy = CongeAnnuelStrategy()
    start_date = date(2024, 8, 19)  # Lundi (férié)
    end_date = date(2024, 8, 20)    # Mardi
    assert strategy.calculate_days(start_date, end_date, HOLIDAYS_SET_FIXTURE) == 1

def test_annuel_calculate_end_date_simple():
    strategy = CongeAnnuelStrategy()
    start_date = date(2024, 8, 5)  # Lundi
    days_to_add = 5
    expected_end_date = date(2024, 8, 9)
    assert strategy.calculate_end_date(start_date, days_to_add, HOLIDAYS_SET_FIXTURE) == expected_end_date

def test_annuel_calculate_end_date_across_weekend_and_holiday():
    strategy = CongeAnnuelStrategy()
    start_date = date(2024, 8, 15) # Jeudi
    days_to_add = 4
    # Compte : J(1), V(2), saute S/D, saute L(férié), M(3), M(4) -> fin Mercredi 21
    expected_end_date = date(2024, 8, 21)
    assert strategy.calculate_end_date(start_date, days_to_add, HOLIDAYS_SET_FIXTURE) == expected_end_date


# --- Tests pour la CongeCalendaireStrategy (jours calendaires) ---

def test_calendaire_calculate_days():
    strategy = CongeCalendaireStrategy()
    start_date = date(2024, 8, 9)   # Vendredi
    end_date = date(2024, 8, 12)  # Lundi
    assert strategy.calculate_days(start_date, end_date, HOLIDAYS_SET_FIXTURE) == 4

def test_calendaire_calculate_end_date():
    strategy = CongeCalendaireStrategy()
    start_date = date(2024, 8, 9)   # Vendredi
    days_to_add = 4
    # Compte V(1), S(2), D(3), L(4) -> fin Lundi 12
    expected_end_date = date(2024, 8, 12)
    assert strategy.calculate_end_date(start_date, days_to_add, HOLIDAYS_SET_FIXTURE) == expected_end_date

def test_calendaire_calculate_days_single_day():
    strategy = CongeCalendaireStrategy()
    start_date = date(2024, 8, 9)
    end_date = date(2024, 8, 9)
    assert strategy.calculate_days(start_date, end_date, HOLIDAYS_SET_FIXTURE) == 1