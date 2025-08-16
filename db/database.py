# Fichier : db/database.py
# Version finale avec méthode pour récupérer le chemin du fichier DB.

import sqlite3
from tkinter import messagebox
import logging
import os
import re
from datetime import datetime

from db.models import Agent, Conge, SoldeAnnuel
from core.constants import SoldeStatus

class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES)
            self.conn.execute("PRAGMA foreign_keys = ON")
            return True
        except sqlite3.Error as e:
            messagebox.showerror("Erreur Base de Données", f"Impossible de se connecter : {e}")
            return False

    def close(self):
        if self.conn: self.conn.close()

    def execute_query(self, query, params=(), fetch=None):
        if not self.conn: raise sqlite3.Error("Pas de connexion à la base de données.")
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            if fetch == "one": return cursor.fetchone()
            if fetch == "all": return cursor.fetchall()
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            self.conn.rollback()
            logging.error(f"Erreur SQL: {query} avec params {params} -> {e}", exc_info=True)
            raise e

    def _handle_data_migration_from_legacy(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(agents)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'solde' in columns or '_solde_legacy' in columns:
                legacy_col_name = 'solde' if 'solde' in columns else '_solde_legacy'
                logging.info(f"Ancienne colonne '{legacy_col_name}' détectée. Lancement de la migration des données...")
                self.conn.execute('BEGIN TRANSACTION')
                
                cursor.execute(f"SELECT id, {legacy_col_name} FROM agents WHERE {legacy_col_name} IS NOT NULL AND {legacy_col_name} > 0")
                legacy_data = cursor.fetchall()

                annee_actuelle = self.get_annee_exercice()
                for agent_id, solde_val in legacy_data:
                    cursor.execute("INSERT INTO soldes_annuels (agent_id, annee, solde, statut) VALUES (?, ?, ?, ?)",
                                   (agent_id, annee_actuelle, solde_val, str(SoldeStatus.ACTIF)))

                cursor.execute("CREATE TABLE agents_new (id INTEGER PRIMARY KEY, nom TEXT NOT NULL, prenom TEXT, ppr TEXT UNIQUE NOT NULL, grade TEXT NOT NULL)")
                cursor.execute("INSERT INTO agents_new (id, nom, prenom, ppr, grade) SELECT id, nom, prenom, ppr, grade FROM agents")
                cursor.execute("DROP TABLE agents")
                cursor.execute("ALTER TABLE agents_new RENAME TO agents")
                
                cursor.execute("REPLACE INTO db_version (version) VALUES (2)")
                self.conn.commit()
                logging.info("Migration des données de solde terminée avec succès.")
                messagebox.showinfo("Mise à jour", "Les données de l'application ont été mises à jour vers la nouvelle version.")
        except sqlite3.Error as e:
            self.conn.rollback()
            logging.error(f"Échec de la migration des données : {e}", exc_info=True)
            raise e

    def run_migrations(self):
        self.execute_query("CREATE TABLE IF NOT EXISTS db_version (version INTEGER PRIMARY KEY)")
        self.execute_query("CREATE TABLE IF NOT EXISTS system_config (config_key TEXT PRIMARY KEY NOT NULL, config_value TEXT NOT NULL)")

        current_version_row = self.execute_query("SELECT version FROM db_version", fetch="one")
        current_version = current_version_row[0] if current_version_row else 0
        
        migrations_path = os.path.join(os.path.dirname(__file__), 'migrations')
        if os.path.exists(migrations_path):
            migrations = {}
            for filename in sorted(os.listdir(migrations_path)):
                match = re.match(r'(\d+)_.*\.sql', filename)
                if match:
                    version = int(match.group(1))
                    if version > current_version:
                        migrations[version] = os.path.join(migrations_path, filename)
            
            if migrations:
                logging.info(f"Migrations SQL à appliquer : {sorted(migrations.keys())}")
                for version in sorted(migrations.keys()):
                    script_path = migrations[version]
                    with open(script_path, 'r', encoding='utf-8') as f: script = f.read()
                    self.conn.cursor().executescript(script)
                    self.execute_query("REPLACE INTO db_version (version) VALUES (?)", (version,))
                messagebox.showinfo("Mise à jour", "La structure de la base de données a été mise à jour.")
        
        if current_version < 2:
            self._handle_data_migration_from_legacy()

    def get_annee_exercice(self):
        result = self.execute_query("SELECT config_value FROM system_config WHERE config_key = 'annee_exercice'", fetch="one")
        if result: return int(result[0])
        else:
            current_year = datetime.now().year
            self.set_annee_exercice(current_year)
            return current_year

    def set_annee_exercice(self, annee):
        self.execute_query("REPLACE INTO system_config (config_key, config_value) VALUES ('annee_exercice', ?)", (str(annee),))

    def get_soldes_by_status(self, statut):
        query = "SELECT s.id, a.nom, a.prenom, s.annee, s.solde FROM soldes_annuels s JOIN agents a ON s.agent_id = a.id WHERE s.statut = ? AND s.solde > 0 ORDER BY a.nom, s.annee"
        return self.execute_query(query, (str(statut),), fetch="all")

    def apurer_soldes_by_ids(self, solde_ids):
        if not solde_ids: return
        placeholders = ','.join('?' for _ in solde_ids)
        query = f"UPDATE soldes_annuels SET solde = 0 WHERE id IN ({placeholders})"
        self.execute_query(query, solde_ids)
    
    def update_solde_by_id(self, solde_id, new_value):
        self.execute_query("UPDATE soldes_annuels SET solde = ? WHERE id = ?", (new_value, solde_id))

    def get_agents(self, term=None, limit=None, offset=None, exclude_id=None):
        q = "SELECT id, nom, prenom, ppr, grade FROM agents"; p, c = [], []
        if term: t = f"%{term.lower()}%"; c.append("(LOWER(nom) LIKE ? OR LOWER(prenom) LIKE ? OR LOWER(ppr) LIKE ?)"); p.extend([t, t, t])
        if exclude_id is not None: c.append("id != ?"); p.append(exclude_id)
        if c: q += " WHERE " + " AND ".join(c)
        q += " ORDER BY nom, prenom"
        if limit is not None: q += " LIMIT ? OFFSET ?"; p.extend([limit, offset])
        agents_rows = self.execute_query(q, tuple(p), fetch="all")
        if not agents_rows: return []
        agents = [Agent.from_db_row(row) for row in agents_rows]
        agent_ids = [agent.id for agent in agents]
        soldes_query = f"SELECT id, agent_id, annee, solde, statut FROM soldes_annuels WHERE agent_id IN ({','.join('?' for _ in agent_ids)})"
        all_soldes_rows = self.execute_query(soldes_query, agent_ids, fetch="all")
        soldes_map = {}
        for row in all_soldes_rows:
            solde_obj = SoldeAnnuel.from_db_row(row)
            if solde_obj.agent_id not in soldes_map: soldes_map[solde_obj.agent_id] = []
            soldes_map[solde_obj.agent_id].append(solde_obj)
        for agent in agents: agent.soldes_annuels = soldes_map.get(agent.id, [])
        return agents

    def get_agent_by_id(self, agent_id):
        row = self.execute_query("SELECT id, nom, prenom, ppr, grade FROM agents WHERE id=?", (agent_id,), fetch="one")
        if not row: return None
        agent = Agent.from_db_row(row)
        soldes_rows = self.execute_query("SELECT id, agent_id, annee, solde, statut FROM soldes_annuels WHERE agent_id = ?", (agent.id,), fetch="all")
        agent.soldes_annuels = [SoldeAnnuel.from_db_row(s_row) for s_row in soldes_rows]
        return agent

    def get_agents_count(self, term=None):
        q, p = "SELECT COUNT(*) FROM agents", []
        if term: t = f"%{term.lower()}%"; q += " WHERE LOWER(nom) LIKE ? OR LOWER(prenom) LIKE ? OR LOWER(ppr) LIKE ?"; p.extend([t, t, t])
        return self.execute_query(q, tuple(p), fetch="one")[0]

    def ajouter_agent(self, nom, prenom, ppr, grade):
        try: return self.execute_query("INSERT INTO agents (nom, prenom, ppr, grade) VALUES (?, ?, ?, ?)",(nom.strip(), prenom.strip(), ppr.strip(), grade.strip()))
        except sqlite3.IntegrityError: return None

    def modifier_agent(self, agent_id, nom, prenom, ppr, grade):
        try:
            self.execute_query("UPDATE agents SET nom=?, prenom=?, ppr=?, grade=? WHERE id=?",(nom.strip(), prenom.strip(), ppr.strip(), grade.strip(), agent_id))
            return True
        except sqlite3.IntegrityError: return False

    def supprimer_agent(self, agent_id):
        self.execute_query("DELETE FROM agents WHERE id=?", (agent_id,)); return True

    def ajouter_conge(self, conge_model):
        return self.execute_query("INSERT INTO conges (agent_id, type_conge, justif, interim_id, date_debut, date_fin, jours_pris) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (conge_model.agent_id, conge_model.type_conge, conge_model.justif, conge_model.interim_id, conge_model.date_debut, conge_model.date_fin, conge_model.jours_pris))

    def supprimer_conge(self, conge_id):
        cert = self.execute_query("SELECT chemin_fichier FROM certificats_medicaux WHERE conge_id = ?", (conge_id,), fetch="one")
        if cert and cert[0] and os.path.exists(cert[0]):
            try: os.remove(cert[0])
            except OSError as e: logging.error(f"Erreur suppression certificat pour conge_id {conge_id}: {e}")
        self.execute_query("DELETE FROM conges WHERE id=?", (conge_id,)); return True

    def get_conges(self, agent_id=None):
        q, p = "SELECT id, agent_id, type_conge, justif, interim_id, date_debut, date_fin, jours_pris, statut FROM conges", ()
        if agent_id: q += " WHERE agent_id=? ORDER BY date_debut DESC"; p = (agent_id,)
        else: q += " ORDER BY date_debut DESC"
        return [Conge.from_db_row(r) for r in self.execute_query(q, p, fetch="all") if r]

    def get_conge_by_id(self, conge_id):
        r = self.execute_query("SELECT id, agent_id, type_conge, justif, interim_id, date_debut, date_fin, jours_pris, statut FROM conges WHERE id=?", (conge_id,), fetch="one")
        return Conge.from_db_row(r) if r else None
        
    def get_overlapping_leaves(self, agent_id, start_date, end_date, conge_id_exclu=None):
        q = "SELECT * FROM conges WHERE agent_id=? AND date_fin >= ? AND date_debut <= ? AND statut = 'Actif'"; p = [agent_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
        if conge_id_exclu: q += " AND id != ?"; p.append(conge_id_exclu)
        return [Conge.from_db_row(r) for r in self.execute_query(q, tuple(p), fetch="all") if r]

    def get_holidays_for_year(self, year):
        return self.execute_query("SELECT date, nom, type FROM jours_feries_personnalises WHERE strftime('%Y', date) = ? ORDER BY date", (str(year),), fetch="all")
        
    def get_certificat_for_conge(self, conge_id):
        return self.execute_query("SELECT * FROM certificats_medicaux WHERE conge_id = ?", (conge_id,), fetch="one")

    def add_or_update_holiday(self, date_sql, name, h_type):
        self.execute_query("REPLACE INTO jours_feries_personnalises (date, nom, type) VALUES (?, ?, ?)", (date_sql, name, h_type)); return True

    def add_holiday(self, date_sql, name, h_type):
        try:
            self.execute_query("INSERT INTO jours_feries_personnalises (date, nom, type) VALUES (?, ?, ?)", (date_sql, name, h_type))
            return True
        except sqlite3.IntegrityError: return False

    def delete_holiday(self, date_sql):
        self.execute_query("DELETE FROM jours_feries_personnalises WHERE date = ?", (date_sql,)); return True
        
    def get_sick_leaves_by_status(self, status='manquant', search_term=None):
        query_base = "SELECT a.nom, a.prenom, a.ppr, c.date_debut, c.date_fin, c.jours_pris FROM conges c JOIN agents a ON c.agent_id = a.id"
        where_clauses = ["c.type_conge = 'Congé de maladie'", "c.statut = 'Actif'"]
        params = []
        if status == 'manquant':
            query_join = "LEFT JOIN certificats_medicaux cm ON c.id = cm.conge_id"
            where_clauses.append("cm.id IS NULL")
        elif status == 'justifie':
            query_join = "INNER JOIN certificats_medicaux cm ON c.id = cm.conge_id"
        else: # 'tous'
            query_join = "LEFT JOIN certificats_medicaux cm ON c.id = cm.conge_id"
        if search_term:
            term = f"%{search_term.lower()}%"
            where_clauses.append("(LOWER(a.nom) LIKE ? OR LOWER(a.prenom) LIKE ? OR LOWER(a.ppr) LIKE ?)")
            params.extend([term, term, term])
        final_query = f"{query_base} {query_join} WHERE {' AND '.join(where_clauses)} ORDER BY c.date_debut DESC"
        return self.execute_query(final_query, tuple(params), fetch="all")
    
    def get_agents_on_leave_today(self):
        query = """
            SELECT a.nom, a.prenom, a.ppr, c.type_conge, c.date_fin
            FROM conges c
            JOIN agents a ON c.agent_id = a.id
            WHERE c.statut = 'Actif'
              AND date('now', 'localtime') BETWEEN date(c.date_debut) AND date(c.date_fin)
            ORDER BY a.nom, a.prenom
        """
        return self.execute_query(query, fetch="all")
        
    def get_db_path(self):
        """Retourne le chemin complet vers le fichier de la base de données."""
        return self.db_file