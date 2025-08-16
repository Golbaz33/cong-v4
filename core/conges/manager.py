# Fichier : core/conges/manager.py
# Version finale et complète avec logique de crédit LIFO pour la restitution des soldes.

import sqlite3
import logging
import os
import shutil
from datetime import datetime, timedelta
from tkinter import messagebox

from utils.date_utils import get_holidays_set_for_period, jours_ouvres, validate_date
from utils.config_loader import CONFIG
from db.models import Agent, Conge
from core.constants import SoldeStatus

class CongeManager:
    def __init__(self, db_manager, certificats_dir):
        self.db = db_manager
        self.certificats_dir = certificats_dir

    def get_annee_exercice(self):
        return self.db.get_annee_exercice()

    def effectuer_glissement_annuel(self):
        self.db.conn.execute('BEGIN TRANSACTION')
        try:
            annee_actuelle = self.get_annee_exercice()
            nouvelle_annee = annee_actuelle + 1
            annee_a_expirer = annee_actuelle - 2
            solde_initial = float(CONFIG['conges'].get('solde_annuel_par_defaut', 22.0))
            all_agents = self.get_all_agents()
            for agent in all_agents:
                self.db.execute_query("INSERT INTO soldes_annuels (agent_id, annee, solde, statut) VALUES (?, ?, ?, ?)",
                                      (agent.id, nouvelle_annee, solde_initial, SoldeStatus.ACTIF))
                self.db.execute_query("UPDATE soldes_annuels SET statut = ? WHERE agent_id = ? AND annee = ?",
                                      (SoldeStatus.EXPIRE, agent.id, annee_a_expirer))
            self.db.set_annee_exercice(nouvelle_annee)
            self.db.conn.commit()
            return True
        except sqlite3.Error as e:
            self.db.conn.rollback()
            logging.error(f"Échec du glissement annuel : {e}", exc_info=True)
            raise e

    def get_soldes_expires(self):
        return self.db.get_soldes_by_status(SoldeStatus.EXPIRE)

    def apurer_soldes(self, solde_ids):
        try:
            self.db.apurer_soldes_by_ids(solde_ids)
            return True
        except sqlite3.Error as e:
            logging.error(f"Échec de l'apurement des soldes : {e}", exc_info=True)
            raise e
    
    def update_soldes_manuellement(self, updated_soldes_data):
        self.db.conn.execute('BEGIN TRANSACTION')
        try:
            for solde_id, new_value in updated_soldes_data.items():
                self.db.update_solde_by_id(solde_id, new_value)
            self.db.conn.commit()
            return True
        except sqlite3.Error as e:
            self.db.conn.rollback()
            logging.error(f"Échec de la mise à jour manuelle des soldes : {e}", exc_info=True)
            raise e

    def get_all_agents(self, **kwargs): return self.db.get_agents(**kwargs)
    def get_agents_count(self, term=None): return self.db.get_agents_count(term=term)
    def get_agent_by_id(self, agent_id): return self.db.get_agent_by_id(agent_id)
    def get_all_conges(self): return self.db.get_conges()
    def get_conges_for_agent(self, agent_id): return self.db.get_conges(agent_id=agent_id)
    def get_conge_by_id(self, conge_id): return self.db.get_conge_by_id(conge_id)
    def get_certificat_for_conge(self, conge_id): return self.db.get_certificat_for_conge(conge_id)
    def get_holidays_for_year(self, year): return self.db.get_holidays_for_year(year)
    def get_sick_leaves_by_status(self, status, search_term=None): return self.db.get_sick_leaves_by_status(status, search_term)
    def get_holidays_set_for_period(self, start_year, end_year): return get_holidays_set_for_period(self.db, start_year, end_year)
    def get_agents_on_leave_today(self): return self.db.get_agents_on_leave_today()
    def add_holiday(self, date_sql, name, h_type): return self.db.add_holiday(date_sql, name, h_type)
    def delete_holiday(self, date_sql): return self.db.delete_holiday(date_sql)
    def add_or_update_holiday(self, date_sql, name, h_type): return self.db.add_or_update_holiday(date_sql, name, h_type)

    def _debiter_solde(self, agent_id, jours_a_prendre):
        if jours_a_prendre <= 0: return
        agent = self.get_agent_by_id(agent_id)
        if agent.get_solde_total_actif() < jours_a_prendre:
            raise ValueError(f"Solde total insuffisant ({agent.get_solde_total_actif()}j) pour décompter {jours_a_prendre}j.")
        
        # Logique FIFO : on trie du plus ancien au plus récent
        soldes_actifs = sorted([s for s in agent.soldes_annuels if s.statut == SoldeStatus.ACTIF], key=lambda s: s.annee)
        
        jours_restants_a_debiter = jours_a_prendre
        for solde_annuel in soldes_actifs:
            if jours_restants_a_debiter == 0: break
            jours_pris_sur_ce_solde = min(solde_annuel.solde, jours_restants_a_debiter)
            nouveau_solde = solde_annuel.solde - jours_pris_sur_ce_solde
            self.db.update_solde_by_id(solde_annuel.id, nouveau_solde)
            jours_restants_a_debiter -= jours_pris_sur_ce_solde
            
        if jours_restants_a_debiter > 0:
            raise sqlite3.Error("Incohérence de solde détectée lors du débit.")

    def _crediter_solde(self, agent_id, jours_a_rendre):
        """
        Crédite les jours sur les soldes actifs de l'agent avec une logique LIFO.
        C'est l'opération inverse exacte du débit.
        """
        if jours_a_rendre <= 0: return
        agent = self.get_agent_by_id(agent_id)
        
        # Logique LIFO : on trie du plus récent au plus ancien
        soldes_actifs = sorted([s for s in agent.soldes_annuels if s.statut == SoldeStatus.ACTIF], key=lambda s: s.annee, reverse=True)
        
        jours_restants_a_rendre = jours_a_rendre
        for solde_annuel in soldes_actifs:
            if jours_restants_a_rendre == 0: break
            
            # On ne peut pas restituer plus que ce que le solde de cette année contient au maximum
            # (par exemple, 22 jours par défaut). C'est une sécurité.
            solde_max_annee = float(CONFIG['conges'].get('solde_annuel_par_defaut', 22.0))
            jours_pouvant_etre_rendus = solde_max_annee - solde_annuel.solde
            
            jours_a_ajouter = min(jours_restants_a_rendre, jours_pouvant_etre_rendus)
            
            if jours_a_ajouter > 0:
                nouveau_solde = solde_annuel.solde + jours_a_ajouter
                self.db.update_solde_by_id(solde_annuel.id, nouveau_solde)
                jours_restants_a_rendre -= jours_a_ajouter

        # S'il reste des jours, c'est probablement car un solde a été apuré entre-temps.
        # On les crédite sur le solde le plus récent.
        if jours_restants_a_rendre > 0 and soldes_actifs:
            solde_le_plus_recent = soldes_actifs[0]
            solde_final = solde_le_plus_recent.solde + jours_restants_a_rendre
            self.db.update_solde_by_id(solde_le_plus_recent.id, solde_final)

    def save_agent(self, agent_data, is_modification=False):
        if is_modification:
            return self.db.modifier_agent(agent_data['id'], agent_data['nom'], agent_data['prenom'], agent_data['ppr'], agent_data['grade'])
        else:
            try:
                agent_id = self.db.ajouter_agent(agent_data['nom'], agent_data['prenom'], agent_data['ppr'], agent_data['grade'])
                if not agent_id:
                    raise sqlite3.IntegrityError("Le PPR est probablement déjà utilisé.")
                
                soldes_initiaux = agent_data.get('soldes', {})
                if not soldes_initiaux:
                    annee_exercice = self.get_annee_exercice()
                    solde_defaut = float(CONFIG['conges'].get('solde_annuel_par_defaut', 22.0))
                    if solde_defaut > 0:
                         soldes_initiaux[annee_exercice] = solde_defaut
                
                for annee, solde_val in soldes_initiaux.items():
                    if solde_val > 0:
                        self.db.execute_query("INSERT INTO soldes_annuels (agent_id, annee, solde, statut) VALUES (?, ?, ?, ?)", 
                                              (agent_id, annee, solde_val, SoldeStatus.ACTIF))
                return agent_id
            except sqlite3.Error as e:
                logging.error(f"Échec de la sauvegarde de l'agent (transaction externe) : {e}")
                raise e

    def delete_agent(self, agent_id):
        return self.db.supprimer_agent(agent_id)

    def handle_conge_submission(self, form_data, is_modification):
        try:
            start_date = validate_date(form_data['date_debut'])
            end_date = validate_date(form_data['date_fin'])
            if not all([form_data['type_conge'], start_date, end_date]) or end_date < start_date:
                raise ValueError("Dates ou type de congé invalides")

            conge_id_exclu = form_data.get('conge_id') if is_modification else None
            overlaps = self.db.get_overlapping_leaves(form_data['agent_id'], start_date, end_date, conge_id_exclu)
            
            if overlaps:
                annual_overlaps = [c for c in overlaps if c.type_conge == 'Congé annuel']
                if len(annual_overlaps) != len(overlaps):
                    raise ValueError("Chevauchement invalide. Vous ne pouvez remplacer que des congés de type 'Congé annuel'.")
                
                if messagebox.askyesno("Confirmation", "Ce congé chevauche un ou plusieurs congés annuels existants.\nVoulez-vous les remplacer ?", master=form_data.get('parent_form')):
                    return self._split_or_replace_leaves(annual_overlaps, form_data)
                else:
                    return False

            self.db.conn.execute('BEGIN TRANSACTION')
            agent_id = form_data['agent_id']; jours_pris = form_data['jours_pris']; type_conge = form_data['type_conge']
            
            if is_modification:
                old_conge = self.get_conge_by_id(form_data['conge_id'])
                if old_conge and old_conge.type_conge in CONFIG['conges']['types_decompte_solde']:
                    self._crediter_solde(old_conge.agent_id, old_conge.jours_pris)
                self.db.supprimer_conge(form_data['conge_id'])

            if type_conge in CONFIG['conges']['types_decompte_solde']:
                self._debiter_solde(agent_id, jours_pris)

            conge_model = Conge(id=None, agent_id=agent_id, type_conge=type_conge, justif=form_data.get('justif'), interim_id=form_data.get('interim_id'), date_debut=start_date.strftime('%Y-%m-%d'), date_fin=end_date.strftime('%Y-%m-%d'), jours_pris=jours_pris)
            new_conge_id = self.db.ajouter_conge(conge_model)
            self.db.conn.commit()

            if new_conge_id and type_conge == "Congé de maladie": self._handle_certificat_save(form_data, new_conge_id)
            return True

        except (ValueError, sqlite3.Error) as e:
            if self.db.conn.in_transaction: self.db.conn.rollback()
            raise e
        except Exception as e:
            if self.db.conn.in_transaction: self.db.conn.rollback()
            logging.error(f"Erreur inattendue soumission congé: {e}", exc_info=True)
            raise e

    def _split_or_replace_leaves(self, annual_overlaps, form_data):
        self.db.conn.execute('BEGIN TRANSACTION')
        try:
            new_start = validate_date(form_data['date_debut'])
            new_end = validate_date(form_data['date_fin'])
            agent_id = form_data['agent_id']
            holidays_set = self.get_holidays_set_for_period(new_start.year - 1, new_end.year + 2)

            for conge in annual_overlaps:
                self._crediter_solde(agent_id, conge.jours_pris)
                self.db.supprimer_conge(conge.id)
            
            type_conge = form_data['type_conge']
            new_conge_model = Conge(id=None, agent_id=agent_id, type_conge=type_conge, justif=form_data.get('justif'), interim_id=form_data.get('interim_id'), date_debut=new_start.strftime('%Y-%m-%d'), date_fin=new_end.strftime('%Y-%m-%d'), jours_pris=form_data['jours_pris'])
            
            if type_conge in CONFIG['conges']['types_decompte_solde']:
                self._debiter_solde(agent_id, new_conge_model.jours_pris)
            new_conge_id = self.db.ajouter_conge(new_conge_model)

            min_start_date = min(c.date_debut for c in annual_overlaps)
            max_end_date = max(c.date_fin for c in annual_overlaps)

            if min_start_date < new_start:
                self._create_leave_segment(agent_id, min_start_date, new_start - timedelta(days=1), holidays_set)
            if max_end_date > new_end:
                self._create_leave_segment(agent_id, new_end + timedelta(days=1), max_end_date, holidays_set)

            self.db.conn.commit()
            if new_conge_id and type_conge == "Congé de maladie": self._handle_certificat_save(form_data, new_conge_id)
            return True
        except (ValueError, sqlite3.Error) as e:
            self.db.conn.rollback(); raise e

    def _create_leave_segment(self, agent_id, start_date, end_date, holidays_set):
        if start_date > end_date: return
        jours = jours_ouvres(start_date, end_date, holidays_set)
        if jours > 0:
            self._debiter_solde(agent_id, jours)
            segment = Conge(None, agent_id, 'Congé annuel', None, None, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), jours)
            self.db.ajouter_conge(segment)

    def delete_conge(self, conge_id):
        conge = self.get_conge_by_id(conge_id)
        if not conge: 
            raise ValueError("Congé introuvable.")
        
        self.db.conn.execute('BEGIN TRANSACTION')
        try:
            if conge.type_conge in CONFIG['conges']['types_decompte_solde']:
                self._crediter_solde(conge.agent_id, conge.jours_pris)
            
            self.db.supprimer_conge(conge_id)
            self.db.conn.commit()
            return True
        except (ValueError, sqlite3.Error) as e:
            self.db.conn.rollback()
            raise e
            
    def _handle_certificat_save(self, form_data, conge_id):
        # Placeholder
        pass

    def find_inconsistent_annual_leaves(self, year):
        # Placeholder
        pass