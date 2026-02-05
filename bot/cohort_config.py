"""
Configuration du système de groupes (remplace le système de cohortes)
"""

# Temps de formation minimum par niveau (en jours)
TEMPS_FORMATION_MINIMUM = {
    1: 2,  # 2 jours pour niveau 1
    2: 3,  # 3 jours pour niveau 2
    3: 3,  # 3 jours pour niveau 3
    4: 3,  # 3 jours pour niveau 4
    5: 3   # 3 jours pour niveau 5
}

# Capacité maximum par groupe (X-Y)
MAX_MEMBRES_PAR_GROUPE = 15

# Nombre de personnes nécessaires pour créer un nouveau groupe depuis la waiting list
MIN_PERSONNES_NOUVEAU_GROUPE = 7

# Lettres disponibles pour les groupes (A-Z)
LETTRES_GROUPES = [chr(i) for i in range(ord('A'), ord('Z') + 1)]  # A, B, C, ..., Z

# Durée de la fenêtre d'examen
DUREE_EXAMEN_NORMALE = 6  # heures
DUREE_EXAMEN_RATTRAPAGE = 6  # heures

# Pourcentage de supplément de temps pour les groupes auto-programmés
# Ex: temps_minimum=2j, supplement=150% → exam dans 2 + (2*1.5) = 5 jours
# Modifie cette valeur pour ajuster le délai d'examen des nouveaux groupes
POURCENTAGE_SUPPLEMENT_FORMATION = 1.5  # 150% du temps minimum ajouté en supplément

# Délais pour les rattrapages selon la note (fraction du temps de formation)
DELAI_RATTRAPAGE = {
    'tres_faible': None,  # < 20% : waiting list
    'faible': 3/4,        # 20-40% : 3/4 du temps
    'moyen': 2/4,         # 40-60% : 1/2 du temps
    'proche': 1/4         # > 60% : 1/4 du temps
}

def get_delai_rattrapage(percentage: float, niveau: int) -> float:
    """
    Calcule le délai de rattrapage en jours selon la note obtenue

    Args:
        percentage: Note obtenue (0-100)
        niveau: Niveau de l'examen raté

    Returns:
        Nombre de jours de délai (ou None si < 20%)
    """
    temps_formation = TEMPS_FORMATION_MINIMUM.get(niveau, 3)

    if percentage < 20:
        return None  # Waiting list
    elif percentage < 40:
        return temps_formation * DELAI_RATTRAPAGE['faible']
    elif percentage < 60:
        return temps_formation * DELAI_RATTRAPAGE['moyen']
    else:  # >= 60
        return temps_formation * DELAI_RATTRAPAGE['proche']

def get_categorie_note(percentage: float) -> str:
    """Retourne la catégorie de note"""
    if percentage < 20:
        return 'tres_faible'
    elif percentage < 40:
        return 'faible'
    elif percentage < 60:
        return 'moyen'
    else:
        return 'proche'
