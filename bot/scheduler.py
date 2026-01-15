import asyncio
from datetime import datetime
from discord.ext import tasks
from database_sql import ReviewDatabaseSQL
class ReviewScheduler:
    """Planificateur de révisions automatiques"""
    
    def __init__(self, bot, database, quiz_manager):
        self.bot = bot
        self.db = ReviewDatabaseSQL()
        self.quiz_manager = quiz_manager
    
    def start(self):
        """Démarre le scheduler"""
        if not self.check_reviews.is_running():
            self.check_reviews.start()
    
    def stop(self):
        """Arrête le scheduler"""
        if self.check_reviews.is_running():
            self.check_reviews.cancel()
    
    @tasks.loop(minutes=1)  # Vérifie toutes les minutes
    async def check_reviews(self):
        """Vérifie les révisions dues et envoie les questions"""
        try:
            all_reviews = self.db.get_all_reviews()
            
            for review in all_reviews:
                # Vérifie si la révision est due
                if self.db.is_review_due(review):
                    user_id = review['user_id']
                    
                    # Évite d'envoyer si l'utilisateur a déjà un quiz actif
                    if user_id not in self.quiz_manager.active_quizzes:
                        await self.quiz_manager.send_review_question(user_id, review)
                        # Pause pour éviter le spam si plusieurs révisions
                        await asyncio.sleep(2)
        
        except Exception as e:
            print(f"❌ Erreur dans check_reviews: {e}")
    
    @check_reviews.before_loop
    async def before_check_reviews(self):
        """Attends que le bot soit prêt avant de démarrer"""
        await self.bot.wait_until_ready()
        print("⏰ Scheduler de révisions initialisé")
