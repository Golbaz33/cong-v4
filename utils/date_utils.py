# Fichier : utils/date_utils.py
# Version finale avec ajout de la fonction manquante.

from datetime import datetime, timedelta, date
from dateutil import parser
import holidays
import sqlite3
import logging
from utils.config_loader import CONFIG

def format_date_for_display(date_str_sql):
    """Convertit une date du format SQL (YYYY-MM-DD) en format affichable (DD/MM/YYYY)."""
    if not date_str_sql: return ""
    try:
        # Si c'est déjà un objet date/datetime, on le formate directement
        if hasattr(date_str_sql, 'strftime'):
            return date_str_sql.strftime("%d/%m/%Y")
        return parser.parse(date_str_sql).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return date_str_sql

# =========================================================================
# CORRECTION : Ajout de la fonction manquante
# =========================================================================
def format_date_for_display_short(date_obj):
    """Convertit un objet date en format affichable court (JJ/MM/AA)."""
    if not date_obj: return ""
    try:
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime("%d/%m/%y")
        return parser.parse(str(date_obj)).strftime("%d/%m/%y")
    except (ValueError, TypeError):
        return str(date_obj)

def validate_date(date_str, dayfirst=True):
    """Valide et convertit une chaîne de caractères en objet datetime."""
    if not date_str: return None
    try:
        return parser.parse(date_str, dayfirst=dayfirst)
    except (ValueError, TypeError):
        return None

def get_holidays_set_for_period(db_manager, start_year, end_year):
    """Charge les jours fériés (officiels et personnalisés) pour une période donnée."""
    country_code = CONFIG['conges']['holidays_country']
    all_h = {}
    for year in range(start_year, end_year + 2):
        all_h.update(holidays.country_holidays(country_code, years=year))
        try:
            if db_manager and db_manager.conn:
                db_h = db_manager.get_holidays_for_year(str(year))
                for date_str, name, type in db_h:
                    all_h[validate_date(date_str).date()] = name
        except sqlite3.Error as e:
            logging.error(f"Erreur lors du chargement des jours fériés pour l'année {year}: {e}")
    return set(all_h.keys())

def jours_ouvres(date_debut, date_fin, holidays_set):
    """Calcule le nombre de jours ouvrés entre deux dates, en excluant les jours fériés."""
    if not date_debut or not date_fin or date_fin < date_debut:
        return 0
    jours = 0
    current_day = date_debut.date() if isinstance(date_debut, datetime) else date_debut
    end_day = date_fin.date() if isinstance(date_fin, datetime) else date_fin
    while current_day <= end_day:
        if current_day.weekday() < 5 and current_day not in holidays_set:
            jours += 1
        current_day += timedelta(days=1)
    return jours

def calculate_reprise_date(end_date, holidays_set):
    """Calcule la date de reprise de service."""
    if not end_date:
        return None
    reprise_date = end_date.date() if isinstance(end_date, datetime) else end_date
    reprise_date += timedelta(days=1)
    while reprise_date.weekday() >= 5 or reprise_date in holidays_set: 
        reprise_date += timedelta(days=1)
    return reprise_date