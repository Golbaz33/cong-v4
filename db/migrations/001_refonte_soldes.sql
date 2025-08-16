-- ##########################################################################
-- ## Version FINALE V3 : Script de migration 100% sûr                   ##
-- ##########################################################################

PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;

-- On crée toutes les tables nécessaires dans leur état final avec "IF NOT EXISTS"
-- Cela garantit que la structure de base existe, peu importe l'état initial.
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY, 
    nom TEXT NOT NULL, 
    prenom TEXT, 
    ppr TEXT UNIQUE NOT NULL, 
    grade TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conges (
    id INTEGER PRIMARY KEY, 
    agent_id INTEGER NOT NULL, 
    type_conge TEXT NOT NULL, 
    justif TEXT, 
    interim_id INTEGER, 
    date_debut TEXT NOT NULL, 
    date_fin TEXT NOT NULL, 
    jours_pris INTEGER NOT NULL, 
    statut TEXT NOT NULL DEFAULT 'Actif', 
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jours_feries_personnalises (
    date TEXT PRIMARY KEY, 
    nom TEXT NOT NULL, 
    type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS certificats_medicaux (
    id INTEGER PRIMARY KEY, 
    conge_id INTEGER NOT NULL UNIQUE, 
    chemin_fichier TEXT NOT NULL, 
    FOREIGN KEY (conge_id) REFERENCES conges(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY NOT NULL, 
    config_value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS soldes_annuels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    agent_id INTEGER NOT NULL, 
    annee INTEGER NOT NULL, 
    solde REAL NOT NULL DEFAULT 0, 
    statut TEXT NOT NULL DEFAULT 'Actif', 
    FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS db_version (
    version INTEGER PRIMARY KEY
);

-- On s'assure que l'index pour les soldes existe
CREATE INDEX IF NOT EXISTS idx_soldes_agent_id ON soldes_annuels (agent_id);

-- On insère la version 1 si elle n'existe pas, pour marquer que la structure de base est là.
INSERT OR IGNORE INTO db_version (version) VALUES (1);

COMMIT;