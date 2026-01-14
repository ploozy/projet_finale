import discord
import asyncio
from datetime import datetime, timedelta
from spaced_rep import SpacedRepetition
from database_sql import ReviewDatabaseSQL

class QuizAnswerView(discord.ui.View):
    """Vue avec boutons dynamiques pour les réponses du quiz"""
    
    def __init__(self, session, question):
        super().__init__(timeout=session.timeout)
        self.session = session
        self.db = ReviewDatabaseSQL()
        self.question = question
        self.answered = False  # Pour éviter les double-clics
        
        # Création dynamique des boutons selon les choix
        for key, value in question['choices'].items():
            button = discord.ui.Button(
                label=f"{key.upper()}) {value}",
                style=discord.ButtonStyle.primary,
                custom_id=f"answer_{key}"
            )
            # Associer le callback à chaque bouton
            button.callback = self.create_callback(key)
            self.add_item(button)
    
    def create_callback(self, answer_key):
        """Crée un callback unique pour chaque bouton"""
        async def button_callback(interaction: discord.Interaction):
            # Vérifier que c'est le bon utilisateur
            if interaction.user.id != self.session.user.id:
                await interaction.response.send_message(
                    "❌ Ce n'est pas votre quiz !",
                    ephemeral=True
                )
                return
            
            # Éviter les double-clics
            if self.answered:
                await interaction.response.send_message(
                    "⚠️ Vous avez déjà répondu à cette question.",
                    ephemeral=True
                )
                return
            
            self.answered = True
            await interaction.response.defer()
            
            # Désactiver tous les boutons
            for item in self.children:
                item.disabled = True
            
            # Mettre à jour le message avec boutons désactivés
            await interaction.message.edit(view=self)
            
            # Traiter la réponse
            await self.session.process_answer(answer_key, self.question)
            
            # Arrêter la View
            self.stop()
        
        return button_callback
    
    async def on_timeout(self):
        """Appelé quand le timeout est atteint"""
        if not self.answered and self.session.timeout:
            await self.session.user.send("⏱️ Temps écoulé ! Question marquée comme incorrecte.")
            await self.session.process_answer(None, self.question)


class QuizManager():
    """Gère la logique des QCM et interactions utilisateur"""
    
    def __init__(self, bot, database, config):
        self.bot = bot
        self.db = database
        self.config = config
        self.active_quizzes = {}  # {user_id: QuizSession}
        self.sr = SpacedRepetition()
    
    async def start_quiz(self, user, course):
        """Démarre un QCM pour un utilisateur"""
        if user.id in self.active_quizzes:
            await user.send("⚠️ Vous avez déjà un QCM en cours. Répondez d'abord aux questions actuelles.")
            return
        
        questions = course.get('questions', [])
        if not questions:
            await user.send("❌ Aucune question disponible pour ce cours")
            return
        
        # Création de la session de quiz
        session = QuizSession(user, course, questions, self)
        self.active_quizzes[user.id] = session
        await session.start()
    
    async def send_review_question(self, user_id, review_data):
        """Envoie une question de révision à un utilisateur"""
        try:
            user = await self.bot.fetch_user(user_id)
            
            # Récupération de la question depuis config
            question = self._find_question_by_id(review_data['question_id'])
            if not question:
                print(f"Question {review_data['question_id']} introuvable")
                return
            
            # Envoi de la question en mode révision
            await user.send("🔔 **Révision programmée**")
            session = QuizSession(user, None, [question], self, is_review=True)
            self.active_quizzes[user_id] = session
            await session.start()
            
        except discord.Forbidden:
            print(f"Impossible d'envoyer MP à {user_id} (MPs bloqués)")
        except Exception as e:
            print(f"Erreur send_review_question: {e}")
    
    def _find_question_by_id(self, question_id):
        """Trouve une question par son ID dans la config"""
        for course in self.config['courses']:
            for q in course.get('questions', []):
                if q['id'] == question_id:
                    return q
        return None
    
    def remove_session(self, user_id):
        """Retire une session de quiz terminée"""
        if user_id in self.active_quizzes:
            del self.active_quizzes[user_id]

class QuizSession:
    """Représente une session de quiz pour un utilisateur"""
    
    def __init__(self, user, course, questions, manager, is_review=False):
        self.user = user
        self.course = course
        self.questions = questions
        self.manager = manager
        self.is_review = is_review
        self.current_index = 0
        self.score = 0
        self.timeout = None if is_review else 60.0 
    
    async def start(self):
        """Démarre la session et envoie la première question"""
        await self.send_question()
    
    async def send_question(self):
        """Envoie la question actuelle à l'utilisateur"""
        if self.current_index >= len(self.questions):
            await self.finish()
            return
        
        question = self.questions[self.current_index]
        
        # Formatage de la question
        choices_text = "\n".join([f"{key.upper()}) {value}" for key, value in question['choices'].items()])
        
        embed = discord.Embed(
            title=f"❓ Question {self.current_index + 1}/{len(self.questions)}",
            description=question['text'],
            color=discord.Color.orange()
        )
        embed.add_field(name="Choix", value=choices_text, inline=False)
        if self.timeout:
            embed.set_footer(text=f"Répondez avec a, b, c ou d ({int(self.timeout)} secondes)")
        else:
            embed.set_footer(text="Répondez avec a, b, c ou d ")
        view = QuizAnswerView(self, question)
        await self.user.send(embed=embed, view=view)
        await view.wait()
    
    # Attente de la réponse avec timeout conditionnel
        try:
            response = await self.manager.bot.wait_for(
            'message',
            check=lambda m: m.author == self.user and isinstance(m.channel, discord.DMChannel),
            timeout=self.timeout  # MODIFIÉ : None pour révisions, 60.0 pour QCM manuels
        )
            await self.process_answer(response.content.strip().lower(), question)
        except asyncio.TimeoutError:
        # Ce bloc ne s'exécute que si timeout n'est pas None
            await self.user.send("⏱️ Temps écoulé ! Question marquée comme incorrecte.")
            await self.process_answer(None, question)
    async def process_answer(self, answer, question):
        """Traite la réponse de l'utilisateur"""
        correct_answer = question['correct']
        is_correct = (answer == correct_answer)
        
        if is_correct:
            await self.user.send("✅ **Correct !**")
            self.score += 1
            quality = 5
        else:
            if answer is None:
                # Cas timeout - message déjà envoyé
                pass
            else:
                await self.user.send(f"❌ **Incorrect.** La bonne réponse était : **{correct_answer.upper()}**")
            quality = 0
    
    # Mise à jour de l'algorithme de révision espacée
        review_data = self.manager.db.get_review(self.user.id, question['id'])
    
        if review_data:
            updated_review = self.manager.sr.update_review(review_data, quality)
        else:
            updated_review = self.manager.sr.calculate_first_review(
            self.user.id, question['id'], quality
        )
    
        self.manager.db.save_review(updated_review)
    
    # Information sur la prochaine révision
        next_time = updated_review['next_review']
        await self.user.send(f"📅 Prochaine révision : {next_time.strftime('%d/%m/%Y %H:%M')}")
    
    # Passage à la question suivante
        self.current_index += 1
        await asyncio.sleep(2)
        await self.send_question()

    async def finish(self):
        """Termine la session de quiz"""
        if not self.is_review:
            embed = discord.Embed(
                title="🎉 QCM terminé !",
                description=f"Score : **{self.score}/{len(self.questions)}**",
                color=discord.Color.green()
            )
            await self.user.send(embed=embed)
        else:
            await self.user.send("✅ Révision terminée !")
        
        # Suppression de la session
        self.manager.remove_session(self.user.id)
