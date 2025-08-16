# Fichier : core/constants.py
# Centralise les valeurs constantes de l'application pour éviter les "Magic Strings".

from enum import Enum

class SoldeStatus(str, Enum):
    """
    Définit les statuts possibles pour un solde annuel.
    
    En héritant de 'str', on peut comparer directement les membres de l'Enum
    avec des chaînes de caractères si nécessaire (ex: valeur venant de la BDD),
    tout en bénéficiant de la robustesse d'une énumération.
    """
    ACTIF = 'Actif'
    EXPIRE = 'Expiré'

    def __str__(self):
        """Assure que la représentation en chaîne est la valeur elle-même."""
        return self.value

# On pourra ajouter d'autres constantes ici à l'avenir, par exemple :
# class CongeStatus(str, Enum):
#     ACTIF = 'Actif'
#     ANNULE = 'Annulé'
#
# class CongeTypes(str, Enum):
#     ANNUEL = 'Congé annuel'
#     MALADIE = 'Congé de maladie'
#     ...