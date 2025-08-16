# Fichier : db/models.py
# Version 5.2 : Utilise l'Enum SoldeStatus pour éviter les magic strings.

from utils.date_utils import validate_date
from core.constants import SoldeStatus # <-- IMPORT DE NOTRE ENUM

class SoldeAnnuel:
    """Représente une ligne de la table soldes_annuels."""
    def __init__(self, id, agent_id, annee, solde, statut):
        self.id = id
        self.agent_id = agent_id
        self.annee = annee
        self.solde = float(solde)
        # On s'assure que le statut est bien un membre de notre Enum
        self.statut = SoldeStatus(statut.strip() if statut else SoldeStatus.ACTIF)

    @classmethod
    def from_db_row(cls, row):
        """Crée une instance de SoldeAnnuel à partir d'une ligne de la base de données."""
        if not row:
            return None
        # id, agent_id, annee, solde, statut
        return cls(id=row[0], agent_id=row[1], annee=row[2], solde=row[3], statut=row[4])


class Agent:
    """Représente un agent avec ses attributs."""
    def __init__(self, id, nom, prenom, ppr, grade, soldes_annuels=None):
        self.id = id
        self.nom = nom.strip() if nom else ""
        self.prenom = prenom.strip() if prenom else ""
        self.ppr = ppr.strip() if ppr else ""
        self.grade = grade.strip() if grade else ""
        self.soldes_annuels = soldes_annuels if soldes_annuels is not None else []

    def __str__(self):
        return f"{self.nom} {self.prenom} (PPR: {self.ppr})"

    @classmethod
    def from_db_row(cls, row):
        """
        Crée une instance de Agent à partir d'une ligne de la table 'agents'.
        """
        if not row:
            return None
        return cls(id=row[0], nom=row[1], prenom=row[2], ppr=row[3], grade=row[4])

    def get_solde_total_actif(self):
        """Calcule et retourne la somme de tous les soldes avec le statut 'Actif'."""
        # On compare maintenant avec la constante au lieu d'une chaîne de caractères
        return sum(s.solde for s in self.soldes_annuels if s.statut == SoldeStatus.ACTIF)


class Conge:
    """Représente un congé avec ses attributs."""
    def __init__(self, id, agent_id, type_conge, justif, interim_id, date_debut, date_fin, jours_pris, statut='Actif'):
        self.id = id
        self.agent_id = agent_id
        self.type_conge = type_conge.strip() if type_conge else ""
        self.justif = justif.strip() if justif else ""
        self.interim_id = interim_id
        self.date_debut = validate_date(date_debut)
        self.date_fin = validate_date(date_fin)
        self.jours_pris = jours_pris
        self.statut = statut.strip() if statut else "Actif"

    def __str__(self):
        debut_str = self.date_debut.strftime('%d/%m/%Y') if self.date_debut else 'N/A'
        fin_str = self.date_fin.strftime('%d/%m/%Y') if self.date_fin else 'N/A'
        return f"Congé {self.type_conge} du {debut_str} au {fin_str} ({self.jours_pris} jours)"

    @classmethod
    def from_db_row(cls, row):
        """Crée une instance de Conge à partir d'une ligne de la base de données."""
        if not row:
            return None
        return cls(
            id=row[0], 
            agent_id=row[1], 
            type_conge=row[2], 
            justif=row[3], 
            interim_id=row[4], 
            date_debut=row[5], 
            date_fin=row[6], 
            jours_pris=row[7],
            statut=row[8]
        )