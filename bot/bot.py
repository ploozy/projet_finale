"""
Bot Discord - Version Clean et Fonctionnelle
✅ Quiz avec boutons
✅ Commande send_course simple
✅ Notifications auto
"""

import discord
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import json

# Keep-alive
from stay_alive import keep_alive
keep_alive()
load_dotenv()

# Initialisation DB
from db_connection import SessionLocal
from models import Utilisateur, ExamResult, Review, CourseQuizResult

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)


# ==================== QUIZ BUTTON ====================
class QuizButton(discord.ui.View):
    """Bouton pour démarrer le quiz"""
    
    def __init__(self, course_id: int):
        super().__init__(timeout=None)
        self.course_id = course_id
    
    @discord.ui.button(label="📝 Faire le Quiz", style=discord.ButtonStyle.primary, custom_id="quiz_button")
    async def quiz_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Envoie le quiz en MP"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Charger le quiz
            quiz_path = f'quizzes/quiz_{self.course_id}.json'
            with open(quiz_path, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)
            
            # Vérifier l'utilisateur
            db = SessionLocal()
            try:
                user = db.query(Utilisateur).filter(
                    Utilisateur.user_id == interaction.user.id
                ).first()
                
                if not user:
                    await interaction.followup.send(
                        "❌ Tu dois d'abord t'inscrire avec `/register`",
                        ephemeral=True
                    )
                    return
                
                # Filtrer avec SM-2
                now = datetime.now()
                questions_to_review = []
                
                for question in quiz_data['questions']:
                    q_id = question['id']
                    
                    review = db.query(Review).filter(
                        Review.user_id == interaction.user.id,
                        Review.question_id == q_id
                    ).first()
                    
                    if not review or review.next_review <= now:
                        questions_to_review.append(question)
                
                if not questions_to_review:
                    await interaction.followup.send(
                        "✅ Tu as déjà révisé toutes les questions !",
                        ephemeral=True
                    )
                    return
                
                # Envoyer en MP
                embed = discord.Embed(
                    title=f"📝 Quiz : {quiz_data['course_title']}",
                    description=f"Tu as **{len(questions_to_review)} question(s)** à réviser.",
                    color=discord.Color.green()
                )
                
                await interaction.user.send(embed=embed)
                await start_quiz_sm2(interaction.user, self.course_id, questions_to_review, db)
                
                await interaction.followup.send(
                    "✅ Quiz envoyé en MP !",
                    ephemeral=True
                )
            
            finally:
                db.close()
        
        except FileNotFoundError:
            await interaction.followup.send(
                f"❌ Quiz {self.course_id} introuvable",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Active tes messages privés !",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ Erreur quiz: {e}")
            await interaction.followup.send(
                f"❌ Erreur : {e}",
                ephemeral=True
            )


async def start_quiz_sm2(member: discord.Member, course_id: int, questions: list, db):
    """Quiz interactif en MP avec SM-2"""
    
    total_questions = len(questions)
    
    for i, question in enumerate(questions):
        # Envoyer la question
        embed = discord.Embed(
            title=f"Question {i+1}/{total_questions}",
            description=question['question'],
            color=discord.Color.blue()
        )
        
        options_text = ""
        for key, value in question['options'].items():
            options_text += f"**{key}.** {value}\n"
        
        embed.add_field(name="Options", value=options_text, inline=False)
        await member.send(embed=embed)
        
        # Attendre réponse
        def check(m):
            return (m.author.id == member.id and 
                    isinstance(m.channel, discord.DMChannel) and 
                    m.content.upper() in ['A', 'B', 'C', 'D'])
        
        try:
            msg = await bot.wait_for('message', check=check, timeout=300)
            user_answer = msg.content.upper()
            correct_answer = question['correct']
            
            # Vérifier
            if user_answer == correct_answer:
                quality = 5
                result_embed = discord.Embed(
                    title="✅ Correct !",
                    description=question.get('explanation', ''),
                    color=discord.Color.green()
                )
            else:
                quality = 0
                result_embed = discord.Embed(
                    title="❌ Incorrect",
                    description=(
                        f"La bonne réponse était : **{correct_answer}**\n\n"
                        f"{question['options'][correct_answer]}\n\n"
                        f"{question.get('explanation', '')}"
                    ),
                    color=discord.Color.red()
                )
            
            await member.send(embed=result_embed)
            
            # SM-2
            review = db.query(Review).filter(
                Review.user_id == member.id,
                Review.question_id == question['id']
            ).first()
            
            if not review:
                review = Review(
                    user_id=member.id,
                    question_id=question['id'],
                    next_review=datetime.now(),
                    interval_days=1.0,
                    repetitions=0,
                    easiness_factor=2.5
                )
                db.add(review)
            
            if quality >= 3:
                if review.repetitions == 0:
                    review.interval_days = 1
                elif review.repetitions == 1:
                    review.interval_days = 6
                else:
                    review.interval_days = review.interval_days * review.easiness_factor
                review.repetitions += 1
            else:
                review.repetitions = 0
                review.interval_days = 1
            
            review.easiness_factor = max(
                1.3,
                review.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            )
            
            review.next_review = datetime.now() + timedelta(days=review.interval_days)
            
            quiz_result = CourseQuizResult(
                user_id=member.id,
                course_id=course_id,
                quiz_question_id=question['id'],
                quality=quality,
                date=datetime.now()
            )
            db.add(quiz_result)
            db.commit()
            
            await asyncio.sleep(2)
        
        except asyncio.TimeoutError:
            await member.send("⏱️ Temps écoulé !")
            return
    
    await member.send(f"🎉 **Quiz terminé !** {total_questions} question(s) répondues.")


# ==================== COMMANDE SEND_COURSE ====================
@bot.command(name='sendcourse')
@commands.has_permissions(administrator=True)
async def send_course_cmd(ctx, course_id: int, channel: discord.TextChannel = None):
    """
    Envoie un cours avec bouton quiz
    Usage: !sendcourse 1 #salon
    """
    if channel is None:
        channel = ctx.channel
    
    try:
        # Charger le quiz
        quiz_path = f'quizzes/quiz_{course_id}.json'
        with open(quiz_path, 'r', encoding='utf-8') as f:
            quiz_data = json.load(f)
            course_title = quiz_data['course_title']
        
        # Créer l'embed
        embed = discord.Embed(
            title=f"📚 {course_title}",
            description="Accède au cours en ligne et teste tes connaissances !",
            color=discord.Color.blue()
        )
        
        course_url = f"https://site-fromation.onrender.com/course/{course_id}"
        
        embed.add_field(
            name="🌐 Lien du cours",
            value=f"[Cliquez ici pour accéder au cours]({course_url})",
            inline=False
        )
        
        embed.add_field(
            name="📝 Quiz Interactif",
            value="Clique sur le bouton ci-dessous !",
            inline=False
        )
        
        # Bouton
        view = QuizButton(course_id)
        
        await channel.send(embed=embed, view=view)
        await ctx.send(f"✅ Cours {course_id} envoyé dans {channel.mention}", delete_after=5)
        await ctx.message.delete()
    
    except FileNotFoundError:
        await ctx.send(f"❌ Quiz {course_id} introuvable. IDs : 1, 2, 3, 4", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}", delete_after=5)


# ==================== NOTIFICATIONS AUTO ====================
@tasks.loop(seconds=30)
async def auto_check_exam_results():
    """Vérifie les nouveaux résultats toutes les 30s"""
    
    if not bot.guilds:
        return
    
    main_guild = bot.guilds[0]
    db = SessionLocal()
    
    try:
        results = db.query(ExamResult).filter(ExamResult.notified == False).all()
        
        if not results:
            return
        
        print(f"🔔 {len(results)} nouveaux résultats")
        
        for result in results:
            try:
                user_db = db.query(Utilisateur).filter(
                    Utilisateur.user_id == result.user_id
                ).first()
                
                if not user_db:
                    continue
                
                member = main_guild.get_member(result.user_id)
                if not member:
                    continue
                
                # Message MP
                if result.passed:
                    message = (
                        f"🎉 **Félicitations !**\n\n"
                        f"Tu as réussi **{result.exam_title}** !\n\n"
                        f"📊 Score : {result.percentage}% ({result.score}/{result.total})\n"
                        f"✅ Seuil : {result.passing_score}%\n\n"
                        f"Continue comme ça ! 💪"
                    )
                else:
                    message = (
                        f"📝 **Résultat d'examen**\n\n"
                        f"Examen : **{result.exam_title}**\n\n"
                        f"📊 Score : {result.percentage}% ({result.score}/{result.total})\n"
                        f"❌ Seuil : {result.passing_score}%\n\n"
                        f"Révise et retente ! 💪"
                    )
                
                try:
                    await member.send(message)
                    print(f"✅ Notification envoyée à {member.name}")
                except discord.Forbidden:
                    print(f"⚠️ MP impossible pour {member.name}")
                
                result.notified = True
                db.commit()
            
            except Exception as e:
                print(f"❌ Erreur notif: {e}")
                continue
    
    finally:
        db.close()


# ==================== ÉVÉNEMENTS ====================
@bot.event
async def on_ready():
    """Démarrage du bot"""
    print(f'✅ {bot.user} connecté')
    print(f'🔗 {len(bot.guilds)} serveur(s)')
    
    # Démarrer les notifications
    if not auto_check_exam_results.is_running():
        auto_check_exam_results.start()
        print("✅ Notifications auto démarrées")


@bot.event
async def on_command_error(ctx, error):
    """Gestion des erreurs"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Permissions insuffisantes", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant : `{error.param}`", delete_after=5)
    else:
        print(f"Erreur : {error}")


# ==================== COMMANDES BASIQUES ====================
@bot.command(name='ping')
async def ping(ctx):
    """Teste le bot"""
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")


@bot.command(name='help_course')
async def help_course(ctx):
    """Aide pour sendcourse"""
    embed = discord.Embed(
        title="📚 Aide - Envoi de Cours",
        description="Voici comment envoyer un cours :",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Commande",
        value="`!sendcourse <id> [#salon]`",
        inline=False
    )
    
    embed.add_field(
        name="Exemples",
        value=(
            "`!sendcourse 1` - Envoie dans le salon actuel\n"
            "`!sendcourse 2 #ressources` - Envoie dans #ressources"
        ),
        inline=False
    )
    
    embed.add_field(
        name="IDs des cours",
        value=(
            "1 = POO\n"
            "2 = Structures de données\n"
            "3 = Exceptions\n"
            "4 = Algorithmique"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)


# ==================== DÉMARRAGE ====================
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant !")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ Erreur démarrage : {e}")
