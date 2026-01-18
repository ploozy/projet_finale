"""
Gestionnaire de révisions SM-2 avec stockage JSON
Pas besoin de SQL pour cette fonctionnalité simple !
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

REVIEWS_FILE = "quiz_reviews.json"


def load_reviews():
    """Charge les révisions depuis le fichier JSON"""
    if os.path.exists(REVIEWS_FILE):
        with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_reviews(reviews):
    """Sauvegarde les révisions dans le fichier JSON"""
    with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False)


def get_user_review(user_id: int, question_id: str):
    """
    Récupère la révision d'un utilisateur pour une question

    Returns:
        dict or None: {
            'next_review': str,
            'interval_days': float,
            'repetitions': int,
            'easiness_factor': float
        }
    """
    reviews = load_reviews()
    user_key = str(user_id)

    if user_key in reviews and question_id in reviews[user_key]:
        return reviews[user_key][question_id]
    return None


def should_review(user_id: int, question_id: str):
    """Vérifie si une question doit être révisée maintenant"""
    review = get_user_review(user_id, question_id)

    if not review:
        # Nouvelle question = toujours à réviser
        return True

    next_review = datetime.fromisoformat(review['next_review'])
    return datetime.now() >= next_review


def update_review_sm2(user_id: int, question_id: str, quality: int, schedule_callback=None):
    """
    Met à jour la révision selon l'algorithme SM-2

    Args:
        user_id: ID Discord de l'utilisateur
        question_id: ID de la question (ex: 'struct_q1')
        quality: 0-5 (0 = mauvais, 5 = parfait)
        schedule_callback: Fonction optionnelle pour planifier le rappel (bot, user_id, question_data, next_review_date)

    Returns:
        dict: Données de révision mises à jour avec next_review_date (datetime)
    """
    reviews = load_reviews()
    user_key = str(user_id)

    # Créer l'entrée utilisateur si elle n'existe pas
    if user_key not in reviews:
        reviews[user_key] = {}

    # Récupérer la révision actuelle ou créer une nouvelle
    if question_id in reviews[user_key]:
        review = reviews[user_key][question_id]
    else:
        review = {
            'interval_days': 1.0,
            'repetitions': 0,
            'easiness_factor': 2.5,
            'next_review': datetime.now().isoformat()
        }

    # Algorithme SM-2
    if quality >= 3:
        # Bonne réponse
        if review['repetitions'] == 0:
            review['interval_days'] = 1
        elif review['repetitions'] == 1:
            review['interval_days'] = 6
        else:
            review['interval_days'] = review['interval_days'] * review['easiness_factor']

        review['repetitions'] += 1
    else:
        # Mauvaise réponse - recommencer
        review['repetitions'] = 0
        review['interval_days'] = 1

    # Ajuster le facteur de facilité
    review['easiness_factor'] = max(
        1.3,
        review['easiness_factor'] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    )

    # Calculer la prochaine révision
    next_review_date = datetime.now() + timedelta(days=review['interval_days'])
    review['next_review'] = next_review_date.isoformat()

    # Sauvegarder
    reviews[user_key][question_id] = review
    save_reviews(reviews)

    # Retourner les données avec la date comme datetime
    return {
        **review,
        'next_review_date': next_review_date
    }


def get_questions_to_review(user_id: int, all_questions: list):
    """
    Filtre les questions qui doivent être révisées maintenant

    Args:
        user_id: ID Discord de l'utilisateur
        all_questions: Liste complète des questions du cours

    Returns:
        list: Questions à réviser
    """
    questions_to_review = []

    for question in all_questions:
        if should_review(user_id, question['id']):
            questions_to_review.append(question)

    return questions_to_review
