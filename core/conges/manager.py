# Fichier : core/conges/manager.py
# Version finale avec une refonte complète de la logique de remplacement pour corriger le bug.

import sqlite3
import logging
import os
import shutil
from datetime import datetime, timedelta
from tkinter import messagebox

from utils.date_utils import get_holidays_set_for_period, jours_ouvres, validate_date
from utils.config_loader import CONFIG
from db.models import Agent, Conge

class CongeManager:
    # --- Les méthodes jusqu'à handle_conge_submission ne changent pas ---
    def __init__(self, db_manager, certificats_dir):
        self.db = db_manager; self.certificats_dir = certificats_dir
    def get_all_agents(self, **kwargs): return self.db.get_agents(**kwargs)
    def get_agents_count(self, term=None): return self.db.get_agents_count(term=term)
    def get_agent_by_id(self, agent_id): return self.db.get_agent_by_id(agent_id)
    def get_all_conges(self): return self.db.get_conges()
    def get_conges_for_agent(self, agent_id): return self.db.get_conges(agent_id=agent_id)
    def get_conge_by_id(self, conge_id): return self.db.get_conge_by_id(conge_id)
    def get_certificat_for_conge(self, conge_id): return self.db.get_certificat_for_conge(conge_id)
    def get_holidays_for_year(self, year): return self.db.get_holidays_for_year(year)
    def add_holiday(self, date_sql, name, h_type): return self.db.add_holiday(date_sql, name, h_type)
    def delete_holiday(self, date_sql): return self.db.delete_holiday(date_sql)
    def add_or_update_holiday(self, date_sql, name, h_type): return self.db.add_or_update_holiday(date_sql, name, h_type)
    def get_maladies_sans_certificat(self): return self.get_sick_leaves_by_status(status='manquant')
    def get_sick_leaves_by_status(self, status, search_term=None): return self.db.get_sick_leaves_by_status(status, search_term)
    def get_holidays_set_for_period(self, start_year, end_year): return get_holidays_set_for_period(self.db, start_year, end_year)
    def get_agents_on_leave_today(self): return self.db.get_agents_on_leave_today()
    def save_agent(self, agent_data, is_modification=False):
        if is_modification: return self.db.modifier_agent(agent_data['id'], agent_data['nom'], agent_data['prenom'], agent_data['ppr'], agent_data['grade'], agent_data['solde'])
        else: return self.db.ajouter_agent(agent_data['nom'], agent_data['prenom'], agent_data['ppr'], agent_data['grade'], agent_data['solde'])
    def delete_agent(self, agent_id): return self.db.supprimer_agent(agent_id)

    def handle_conge_submission(self, form_data, is_modification):
        try:
            start_date = validate_date(form_data['date_debut']); end_date = validate_date(form_data['date_fin'])
            if not all([form_data['type_conge'], start_date, end_date]) or end_date < start_date:
                raise ValueError("Dates ou type de congé invalides")
            if form_data['jours_pris'] <= 0 and form_data['type_conge'] != 'Congé annuel':
                 raise ValueError("La durée du congé doit être positive")
            
            conge_id_exclu = form_data.get('conge_id') if is_modification else None
            overlaps = self.db.get_overlapping_leaves(form_data['agent_id'], start_date, end_date, conge_id_exclu)
            
            if overlaps:
                annual_overlaps = [c for c in overlaps if c.type_conge == 'Congé annuel']
                if len(annual_overlaps) != len(overlaps):
                    raise ValueError("Chevauchement invalide. Vous ne pouvez remplacer que des congés de type 'Congé annuel'.")
                
                if messagebox.askyesno("Confirmation", "Ce congé va remplacer un ou plusieurs congés annuels. Continuer ?"):
                    return self.split_or_replace_leaves(annual_overlaps, form_data, old_conge_id_to_delete=conge_id_exclu)
                else:
                    return False

            # Logique standard sans chevauchement
            conge_model = Conge(id=form_data.get('conge_id'), agent_id=form_data['agent_id'], type_conge=form_data['type_conge'], justif=form_data.get('justif'), interim_id=form_data.get('interim_id'), date_debut=start_date.strftime('%Y-%m-%d'), date_fin=end_date.strftime('%Y-%m-%d'), jours_pris=form_data['jours_pris'])
            if is_modification: 
                conge_id = self.db.modifier_conge(form_data['conge_id'], conge_model)
            else: 
                conge_id = self.db.ajouter_conge(conge_model)
            if conge_id and form_data['type_conge'] == "Congé de maladie":
                 self._handle_certificat_save(form_data, is_modification, conge_id)
            return True if conge_id else False
        except (ValueError, sqlite3.Error) as e:
            raise e
        except Exception as e:
            logging.error(f"Erreur soumission congé: {e}", exc_info=True); raise e

    def split_or_replace_leaves(self, annual_overlaps, form_data, old_conge_id_to_delete=None):
        """
        Réécriture complète de la logique pour être simple et robuste.
        Elle supprime les anciens congés et recrée ce qui est nécessaire.
        """
        logging.info(f"Remplacement transactionnel de {len(annual_overlaps)} congés annuels.")
        try:
            self.db.conn.execute('BEGIN TRANSACTION')
            cursor = self.db.conn.cursor()

            # Si on modifie un congé, on le supprime (gère le solde correctement)
            if old_conge_id_to_delete:
                self.db._supprimer_conge_no_commit(cursor, old_conge_id_to_delete)

            new_start = validate_date(form_data['date_debut'])
            new_end = validate_date(form_data['date_fin'])
            holidays_set = self.get_holidays_set_for_period(new_start.year - 1, new_end.year + 2)
            
            for conge in annual_overlaps:
                # 1. On supprime le congé annuel. La fonction _supprimer_conge_no_commit
                # s'occupe de restaurer le solde, de supprimer le certificat, etc.
                self.db._supprimer_conge_no_commit(cursor, conge.id)

                # 2. On recrée les segments restants. La fonction _create_leave_segment
                # s'occupe de débiter le solde correctement pour ces nouveaux segments.
                if conge.date_debut < new_start:
                    self._create_leave_segment(cursor, conge.agent_id, conge.date_debut, new_start - timedelta(days=1), holidays_set)
                if conge.date_fin > new_end:
                    self._create_leave_segment(cursor, conge.agent_id, new_end + timedelta(days=1), conge.date_fin, holidays_set)

            # 3. On ajoute le nouveau congé (maladie, etc.)
            new_conge_model = Conge(id=None, agent_id=form_data['agent_id'], type_conge=form_data['type_conge'], justif=form_data.get('justif'), interim_id=form_data.get('interim_id'), date_debut=new_start.strftime('%Y-%m-%d'), date_fin=new_end.strftime('%Y-%m-%d'), jours_pris=form_data['jours_pris'])
            new_conge_id = self.db._ajouter_conge_no_commit(cursor, new_conge_model)
            
            if new_conge_id and form_data['type_conge'] == "Congé de maladie":
                self._handle_certificat_save(form_data, False, new_conge_id)
            
            self.db.conn.commit()
            return True
        except (sqlite3.Error, ValueError) as e:
            self.db.conn.rollback(); raise e

    def _create_leave_segment(self, cursor, agent_id, start_date, end_date, holidays_set):
        if start_date > end_date: return
        jours = jours_ouvres(start_date, end_date, holidays_set)
        segment = Conge(None, agent_id, 'Congé annuel', None, None, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), jours)
        self.db._ajouter_conge_no_commit(cursor, segment)

    # ... (Le reste du fichier, à partir de delete_conge, est inchangé)
    def delete_conge(self, conge_id):
        conge = self.db.get_conge_by_id(conge_id)
        if not conge: raise ValueError("Le congé sélectionné n'a pas pu être trouvé.")
        try:
            if conge.statut == 'Annulé':
                logging.info(f"Suppression simple du congé annulé ID {conge_id}."); self.db.execute_query("DELETE FROM conges WHERE id=?", (conge_id,)); return True
            else: return self.revoke_split_on_delete(conge_id)
        except Exception as e:
            logging.error(f"Erreur lors de la suppression du congé {conge_id}: {e}", exc_info=True); raise e
    def revoke_split_on_delete(self, conge_id_to_delete):
        logging.info(f"Début de la suppression/restauration pour le congé ID {conge_id_to_delete}."); conge_to_delete = self.db.get_conge_by_id(conge_id_to_delete);
        if not conge_to_delete: return False
        agent_id = conge_to_delete.agent_id
        try:
            parent_conge_row = self.db.execute_query(
                """SELECT * FROM conges WHERE agent_id = ? AND type_conge = 'Congé annuel' AND statut = 'Annulé' AND ( (date(date_debut) <= date(?) AND date(date_fin) >= date(?)) OR (date(date_debut) >= date(?) AND date(date_fin) <= date(?)) ) ORDER BY date_debut DESC LIMIT 1""",
                (agent_id, conge_to_delete.date_debut.strftime('%Y-%m-%d'), conge_to_delete.date_fin.strftime('%Y-%m-%d'), conge_to_delete.date_debut.strftime('%Y-%m-%d'), conge_to_delete.date_fin.strftime('%Y-%m-%d')), fetch="one"
            )
            if parent_conge_row:
                parent_conge = Conge.from_db_row(parent_conge_row); logging.info(f"Restauration détectée. Parent ID: {parent_conge.id}."); self.db.conn.execute('BEGIN TRANSACTION'); cursor = self.db.conn.cursor(); self.db._supprimer_conge_no_commit(cursor, conge_id_to_delete)
                all_active_conges = [Conge.from_db_row(r) for r in cursor.execute("SELECT * FROM conges WHERE agent_id=? AND statut='Actif'", (agent_id,)).fetchall()]
                for conge in all_active_conges:
                    if conge.date_debut >= parent_conge.date_debut and conge.date_fin <= parent_conge.date_fin: self.db._supprimer_conge_no_commit(cursor, conge.id)
                cursor.execute("UPDATE conges SET statut = 'Actif' WHERE id = ?", (parent_conge.id,))
                if parent_conge.type_conge in CONFIG['conges']['types_decompte_solde']: cursor.execute("UPDATE agents SET solde = solde - ? WHERE id = ?", (parent_conge.jours_pris, agent_id))
                self.db.conn.commit(); return True
            else:
                logging.info(f"Aucun parent trouvé. Suppression simple."); self.db.supprimer_conge(conge_id_to_delete); return True
        except (sqlite3.Error, ValueError) as e:
            if self.db.conn.in_transaction: self.db.conn.rollback()
            logging.error(f"Échec de la transaction: {e}", exc_info=True); raise e
    def find_inconsistent_annual_leaves(self, year):
        inconsistent_leaves = [];
        try:
            query = "SELECT * FROM conges WHERE type_conge = 'Congé annuel' AND statut = 'Actif' AND strftime('%Y', date_debut) = ?"; leaves_rows = self.db.execute_query(query, (str(year),), fetch="all")
            if not leaves_rows: return []
            holidays_set = self.get_holidays_set_for_period(year, year)
            for row in leaves_rows:
                conge = Conge.from_db_row(row); recalculated_days = jours_ouvres(conge.date_debut, conge.date_fin, holidays_set)
                if conge.jours_pris != recalculated_days: inconsistent_leaves.append((conge, recalculated_days))
        except Exception as e:
            logging.error(f"Erreur lors de l'audit des congés pour l'année {year}: {e}", exc_info=True); return []
        return inconsistent_leaves
    def _handle_certificat_save(self, form_data, is_modification, conge_id):
        new_path = form_data.get('cert_path'); original_path = form_data.get('original_cert_path')
        if not new_path or not conge_id: return
        if os.path.exists(new_path) and new_path != original_path:
            try:
                filename = f"cert_{form_data['agent_ppr']}_{conge_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{os.path.splitext(new_path)[1]}"; dest_path = os.path.join(self.certificats_dir, filename); shutil.copy(new_path, dest_path)
                cert_model = type('Certificat', (object,), {'duree_jours': form_data['jours_pris'], 'chemin_fichier': dest_path})(); self.db.execute_query("REPLACE INTO certificats_medicaux (conge_id, duree_jours, chemin_fichier) VALUES (?, ?, ?)", (conge_id, cert_model.duree_jours, cert_model.chemin_fichier))
                if original_path and os.path.exists(original_path): os.remove(original_path)
            except Exception as e: logging.error(f"Erreur sauvegarde certificat: {e}", exc_info=True)
        elif not new_path and original_path:
            try:
                self.db.execute_query("DELETE FROM certificats_medicaux WHERE conge_id = ?", (conge_id,));
                if os.path.exists(original_path): os.remove(original_path)
            except Exception as e: logging.error(f"Impossible de supprimer l'ancien certificat pour conge_id {conge_id}: {e}")