# Fichier : main.py
# Version finale avec gestion du redémarrage après restauration.

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

    # --- Boucle de l'application pour permettre le redémarrage ---
    restart_app = True
    while restart_app:
        restart_app = False # On suppose qu'on ne redémarrera pas

        # --- Étape 6 : Initialiser les composants principaux ---
        db_manager = DatabaseManager(DB_PATH_ABS)
        if not db_manager.connect():
            sys.exit(1)
            
        try:
            db_manager.run_migrations()
        except Exception as e:
            logging.critical(f"Échec critique du processus de migration. Arrêt de l'application. Erreur : {e}")
            sys.exit(1)
            
        conge_manager = CongeManager(db_manager, CERTIFICATS_DIR_ABS)
        
        # --- Étape 7 : Lancer l'application ---
        print(f"--- Lancement de {CONFIG['app']['title']} v{CONFIG['app']['version']} ---")
        app = MainWindow(conge_manager)
        app.mainloop()
        
        # --- Étape 8 : Nettoyage à la fermeture ---
        if hasattr(app, 'restart_on_close') and app.restart_on_close:
            restart_app = True # On indique qu'il faut refaire un tour de boucle
        
        db_manager.close()
    
    print("--- Application fermée, connexion à la base de données terminée. ---")