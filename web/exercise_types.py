"""
Système de validation pour les différents types d'exercices
Supporte : QCM, Texte à trous, Association, Écriture libre, Ordre de mots, Traduction
"""


def normalize_arabic_text(text):
    """
    Normalise le texte arabe pour la comparaison
    - Retire les espaces en début/fin
    - Normalise les espaces multiples
    - Retire les diacritiques optionnels (tachkil)
    """
    if not text:
        return ""

    # Retirer les espaces en début/fin
    text = text.strip()

    # Normaliser les espaces multiples
    text = ' '.join(text.split())

    # Diacritiques arabes à ignorer pour la comparaison (optionnel)
    # Kasra, Fatha, Damma, Sukun, Shadda, Tanwin, etc.
    diacritics = ['\u064B', '\u064C', '\u064D', '\u064E', '\u064F',
                  '\u0650', '\u0651', '\u0652', '\u0653', '\u0654',
                  '\u0655', '\u0656', '\u0657', '\u0658', '\u0670']

    for diacritic in diacritics:
        text = text.replace(diacritic, '')

    return text


def validate_qcm(question, user_answer):
    """
    Valide une question QCM classique

    Args:
        question: dict avec 'correct' (str: "a", "b", "c", "d")
        user_answer: str ("a", "b", "c", "d")

    Returns:
        bool: True si correct
    """
    if not user_answer:
        return False

    return user_answer.lower() == question['correct'].lower()


def validate_fill_blank(question, user_answer):
    """
    Valide un exercice de texte à trous

    Args:
        question: dict avec 'correct' (int: index de la bonne réponse dans options)
        user_answer: str (index sous forme de string)

    Returns:
        bool: True si correct
    """
    if not user_answer:
        return False

    try:
        user_index = int(user_answer)
        return user_index == question['correct']
    except (ValueError, TypeError):
        return False


def validate_matching(question, user_answers):
    """
    Valide un exercice d'association

    Args:
        question: dict avec 'pairs' (list de {ar, fr})
        user_answers: dict {ar_index: fr_index}

    Returns:
        bool: True si toutes les associations sont correctes
    """
    if not user_answers or not isinstance(user_answers, dict):
        return False

    # Vérifier que toutes les paires sont correctement associées
    pairs = question['pairs']

    # Pour chaque paire, vérifier que l'utilisateur a associé le bon français
    for i, pair in enumerate(pairs):
        user_choice = user_answers.get(str(i))

        if user_choice is None:
            return False

        try:
            user_fr_index = int(user_choice)
            # Vérifier que l'index correspond à la bonne traduction
            if user_fr_index != i:
                return False
        except (ValueError, TypeError):
            return False

    return True


def validate_text_input(question, user_answer):
    """
    Valide un exercice d'écriture libre stricte

    Args:
        question: dict avec 'correct' (str) ou 'accept' (list de str)
        user_answer: str

    Returns:
        bool: True si la réponse correspond exactement (après normalisation)
    """
    if not user_answer:
        return False

    # Normaliser la réponse utilisateur
    normalized_answer = normalize_arabic_text(user_answer)

    # Vérifier si 'accept' existe (plusieurs réponses possibles)
    if 'accept' in question:
        for accepted in question['accept']:
            if normalized_answer == normalize_arabic_text(accepted):
                return True
        return False

    # Sinon, utiliser 'correct'
    return normalized_answer == normalize_arabic_text(question['correct'])


def validate_word_order(question, user_answer):
    """
    Valide un exercice d'ordre de mots

    Args:
        question: dict avec 'correct_order' (list de str)
        user_answer: str (indices séparés par des virgules, ex: "0,2,1")

    Returns:
        bool: True si l'ordre est correct
    """
    if not user_answer:
        return False

    try:
        # Parser la réponse utilisateur (indices séparés par virgules)
        user_indices = [int(x.strip()) for x in user_answer.split(',')]

        # Reconstruire la phrase avec les indices de l'utilisateur
        words_shuffled = question['words']
        user_sentence = [words_shuffled[i] for i in user_indices]

        # Comparer avec l'ordre correct
        return user_sentence == question['correct_order']
    except (ValueError, IndexError, TypeError):
        return False


def validate_translation(question, user_answer):
    """
    Valide un exercice de traduction FR → AR

    Args:
        question: dict avec 'correct_ar' (str) ou 'accept' (list de str)
        user_answer: str

    Returns:
        bool: True si la traduction est acceptée
    """
    if not user_answer:
        return False

    # Normaliser la réponse
    normalized_answer = normalize_arabic_text(user_answer)

    # Vérifier si plusieurs réponses sont acceptées
    if 'accept' in question:
        for accepted in question['accept']:
            if normalized_answer == normalize_arabic_text(accepted):
                return True
        return False

    # Sinon, utiliser 'correct_ar'
    return normalized_answer == normalize_arabic_text(question['correct_ar'])


def validate_question(question, user_answer):
    """
    Fonction principale de validation - détecte le type et valide

    Args:
        question: dict avec 'type' et données spécifiques
        user_answer: réponse de l'utilisateur (format dépend du type)

    Returns:
        bool: True si correct
    """
    question_type = question.get('type', 'qcm')

    validators = {
        'qcm': validate_qcm,
        'fill_blank': validate_fill_blank,
        'matching': validate_matching,
        'text_input': validate_text_input,
        'word_order': validate_word_order,
        'translation': validate_translation
    }

    validator = validators.get(question_type)

    if not validator:
        print(f"⚠️ Type de question inconnu: {question_type}")
        return False

    return validator(question, user_answer)
