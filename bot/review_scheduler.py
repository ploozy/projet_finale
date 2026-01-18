"""
Planificateur de révisions automatiques avec rappels par MP
Utilise APScheduler pour envoyer les questions aux dates/heures exactes
"""

import asyncio
import discord
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from quiz_reviews_manager import get_user_review, load_reviews
import json
import os

PENDING_QUESTIONS_FILE = "pending_questions.json"

scheduler = AsyncIOScheduler()


def load_pending_questions():
    """Charge les questions en attente de réponse"""
    if os.path.exists(PENDING_QUESTIONS_FILE):
        with open(PENDING_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_pending_questions(pending):
    """Sauvegarde les questions en attente"""
    with open(PENDING_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)


def has_pending_question(user_id: int):
    """Vérifie si l'utilisateur a une question en attente de réponse"""
    pending = load_pending_questions()
    user_key = str(user_id)
    return user_key in pending and pending[user_key] is not None


def add_to_queue(user_id: int, question_data: dict):
    """Ajoute une question à la file d'attente de l'utilisateur"""
    pending = load_pending_questions()
    user_key = str(user_id)

    if user_key not in pending:
        pending[user_key] = {
            'current': None,
            'queue': []
        }

    # Si pas de question en cours, elle devient la question courante
    if pending[user_key]['current'] is None:
        pending[user_key]['current'] = question_data
    else:
        # Sinon, ajout à la file d'attente
        pending[user_key]['queue'].append(question_data)

    save_pending_questions(pending)


def get_pending_question(user_id: int):
    """Récupère la question en attente pour un utilisateur"""
    pending = load_pending_questions()
    user_key = str(user_id)

    if user_key in pending and pending[user_key]['current']:
        return pending[user_key]['current']
    return None


def complete_question(user_id: int):
    """Marque la question courante comme répondue et passe à la suivante"""
    pending = load_pending_questions()
    user_key = str(user_id)

    if user_key not in pending:
        return None

    # Retirer la question courante
    pending[user_key]['current'] = None

    # S'il y a des questions en attente, prendre la première
    if pending[user_key]['queue']:
        next_question = pending[user_key]['queue'].pop(0)
        pending[user_key]['current'] = next_question
        save_pending_questions(pending)
        return next_question
    else:
        # Plus de questions en attente
        save_pending_questions(pending)
        return None


async def send_review_question(bot, user_id: int, question_data: dict):
    """
    Envoie une question de révision en MP à l'utilisateur

    Args:
        bot: Instance du bot Discord
        user_id: ID Discord de l'utilisateur
        question_data: Dict contenant les infos de la question
    """
    try:
        user = await bot.fetch_user(user_id)

        # Vérifier si l'utilisateur a déjà une question en attente
        if has_pending_question(user_id):
            print(f"⏸️ Question mise en attente pour {user_id} (question en cours)")
            add_to_queue(user_id, question_data)
            return

        # Ajouter comme question courante
        add_to_queue(user_id, question_data)

        # Créer l'embed de la question
        embed = discord.Embed(
            title="🔔 Révision programmée",
            description=question_data['question'],
            color=discord.Color.blue()
        )

        # Ajouter les options
        options_text = ""
        for idx, option in enumerate(question_data['options']):
            letter = chr(65 + idx)  # A, B, C, D
            options_text += f"**{letter}.** {option}\n"

        embed.add_field(
            name="Options",
            value=options_text,
            inline=False
        )

        embed.set_footer(text="Réponds avec les boutons ci-dessous quand tu es prêt !")

        # Créer la vue avec boutons
        from bot import ReviewQuestionView
        view = ReviewQuestionView(question_data, user_id)

        await user.send(embed=embed, view=view)
        print(f"📬 Question envoyée à {user.name} (ID: {user_id})")

    except discord.Forbidden:
        print(f"❌ Impossible d'envoyer un MP à {user_id} (MPs désactivés)")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de la question à {user_id}: {e}")


def schedule_review(bot, user_id: int, question_data: dict, next_review_date: datetime):
    """
    Planifie l'envoi d'une question de révision à une date précise

    Args:
        bot: Instance du bot Discord
        user_id: ID Discord de l'utilisateur
        question_data: Dict avec les infos de la question
        next_review_date: datetime de la prochaine révision
    """
    # Créer une tâche planifiée
    trigger = DateTrigger(run_date=next_review_date)

    scheduler.add_job(
        send_review_question,
        trigger=trigger,
        args=[bot, user_id, question_data],
        id=f"review_{user_id}_{question_data['id']}",
        replace_existing=True,
        misfire_grace_time=3600  # 1h de tolérance si le bot était éteint
    )

    print(f"⏰ Révision planifiée pour {user_id} - Question {question_data['id']} à {next_review_date}")


def start_scheduler():
    """Démarre le planificateur"""
    if not scheduler.running:
        scheduler.start()
        print("✅ Planificateur de révisions démarré")


def load_scheduled_reviews(bot, quizzes_data):
    """
    Charge toutes les révisions planifiées depuis quiz_reviews.json
    À appeler au démarrage du bot
    """
    reviews = load_reviews()
    count = 0

    for user_id_str, user_reviews in reviews.items():
        user_id = int(user_id_str)

        for question_id, review_data in user_reviews.items():
            # Récupérer la date de prochaine révision
            next_review = datetime.fromisoformat(review_data['next_review'])

            # Si la date est passée, planifier pour maintenant
            if next_review < datetime.now():
                next_review = datetime.now()

            # Trouver la question dans quizzes_data
            question_data = None
            for course in quizzes_data['courses']:
                for q in course['questions']:
                    if q['id'] == question_id:
                        question_data = q
                        break
                if question_data:
                    break

            if question_data:
                schedule_review(bot, user_id, question_data, next_review)
                count += 1

    print(f"📅 {count} révisions planifiées chargées au démarrage")
