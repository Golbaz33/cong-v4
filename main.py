# Fichier : main.py
# Version finale avec fermeture propre de la connexion DB.

import tkinter as tk
from tkinter import messagebox
import sys
import os
import logging

# --- Étape 1 : Définir les chemins de base ---
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# --- Étape 2 : Charger la configuration AVANT tout le reste ---
try:
    from utils.config_loader import load_config, CONFIG
    load_config(CONFIG_PATH)
except Exception as e:
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Erreur Critique de Configuration", f"Impossible de charger la configuration:\n{e}")
    sys.exit(1)

# --- Étape 3 : Importer les autres composants de l'architecture ---
from db.database import DatabaseManager
from core.conges.manager import CongeManager
from ui.main_window import MainWindow


if __name__ == "__main__":
    # --- Étape 4 : Vérifier les dépendances externes ---
    try:
        import tkcalendar, dateutil, holidays, yaml, openpyxl
    except ImportError as e:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Bibliothèque Manquante", f"Une bibliothèque nécessaire est manquante : {e.name}.\n\nVeuillez l'installer avec la commande :\npip install -r requirements.txt")
        sys.exit(1)

    # --- Étape 5 : Préparer l'environnement ---
    CERTIFICATS_DIR_ABS = os.path.join(BASE_DIR, CONFIG['db']['certificates_dir'])
    if not os.path.exists(CERTIFICATS_DIR_ABS):
        os.makedirs(CERTIFICATS_DIR_ABS)
        
    DB_PATH_ABS = os.path.join(BASE_DIR, CONFIG['db']['filename'])
    
    LOG_FILE_PATH = os.path.join(BASE_DIR, "conges.log")
    logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # --- Étape 6 : Initialiser les composants principaux ---
    db_manager = DatabaseManager(DB_PATH_ABS)
    if not db_manager.connect():
        sys.exit(1)
        
    db_manager.create_db_tables()
    conge_manager = CongeManager(db_manager, CERTIFICATS_DIR_ABS)
    
    # --- Étape 7 : Lancer l'application ---
    print(f"--- Lancement de {CONFIG['app']['title']} v{CONFIG['app']['version']} ---")
    app = MainWindow(conge_manager)
    app.mainloop()
    
    # --- Étape 8 : Nettoyage à la fermeture ---
    # AMÉLIORATION : Assure une fermeture propre de la connexion à la base de données
    # lorsque la fenêtre principale est fermée.
    db_manager.close()
    print("--- Application fermée, connexion à la base de données terminée. ---")