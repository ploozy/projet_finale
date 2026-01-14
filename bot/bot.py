import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import json
from datetime import datetime
import asyncio
from quiz import QuizManager
from scheduler import ReviewScheduler
from aiohttp import web
from stay_alive import keep_alive

# ✅ UTILISATION DE POSTGRESQL
from cohorte_manager_sql import CohortManagerSQL
from database_sql import ReviewDatabaseSQL
from exam_result_database_sql import ExamResultDatabaseSQL

keep_alive()
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Chargement de la config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Initialisation des managers (PostgreSQL)
cohort_manager = CohortManagerSQL()
review_db = ReviewDatabaseSQL()
exam_db = ExamResultDatabaseSQL()
quiz_manager = QuizManager(bot, review_db, config)
scheduler = ReviewScheduler(bot, review_db, quiz_manager)


class BotHTTPServer:
    """Serveur HTTP pour recevoir les requêtes du site web"""
    def __init__(self, bot, quiz_manager, config, exam_db):
        self.bot = bot
        self.quiz_manager = quiz_manager
        self.config = config
        self.exam_db = exam_db
        self.app = web.Application()
        self.app.router.add_post('/api/send_quiz', self.handle_send_quiz)
        self.app.router.add_post('/api/mark_notified', self.handle_mark_notified)
        self.runner = None

    async def handle_send_quiz(self, request):
        """Endpoint pour envoyer un quiz en MP"""
        try:
            data = await request.json()
            user_id = int(data['user_id'])
            course_id = int(data['course_id'])
            
            course = next((c for c in self.config['courses'] if c['id'] == course_id), None)
            if not course:
                return web.json_response({
                    'success': False,
                    'message': 'Cours introuvable'
                }, status=404)
            
            try:
                user = await self.bot.fetch_user(user_id)
                
                if user_id in self.quiz_manager.active_quizzes:
                    return web.json_response({
                        'success': False,
                        'message': 'QCM déjà en cours'
                    }, status=400)
                
                await self.quiz_manager.start_quiz(user, course)
                
                return web.json_response({
                    'success': True,
                    'message': f'QCM envoyé à {user.name}'
                })
                
            except discord.Forbidden:
                return web.json_response({
                    'success': False,
                    'message': 'MPs bloqués'
                }, status=403)
            except Exception as e:
                return web.json_response({
                    'success': False,
                    'message': str(e)
                }, status=500)
                
        except Exception as e:
            print(f"Erreur handle_send_quiz: {e}")
            return web.json_response({
                'success': False,
                'message': str(e)
            }, status=500)

    async def handle_mark_notified(self, request):
        """Marque des résultats comme notifiés"""
        try:
            data = await request.json()
            for result in data.get('results', []):
                self.exam_db.mark_as_notified(
                    result['user_id'],
                    result['exam_id'],
                    result['date']
                )
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)

    async def start(self):
        """Démarre le serveur HTTP"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', 8080)
        await site.start()
        print("✅ Serveur HTTP démarré sur port 8080")

    async def stop(self):
        """Arrête le serveur HTTP"""
        if self.runner:
            await self.runner.cleanup()


# Initialisation du serveur HTTP
http_server = BotHTTPServer(bot, quiz_manager, config, exam_db)


@bot.event
async def on_ready():
    print(f'✅ Bot connecté en tant que {bot.user}')
    
    # Démarrer le scheduler
    scheduler.start()
    
    # Démarrer le serveur HTTP
    await http_server.start()
    
    print(f'📊 Guildes : {len(bot.guilds)}')


@bot.command(name='send_course')
@commands.has_permissions(administrator=True)
async def send_course(ctx, course_number: int):
    """Envoie un cours avec bouton QCM (admin uniquement)"""
    
    course = next((c for c in config['courses'] if c['id'] == course_number), None)
    
    if not course:
        await ctx.send(f"❌ Cours {course_number} introuvable")
        return
    
    embed = discord.Embed(
        title=f"📚 {course['title']}",
        description="Cliquez sur le lien pour accéder au cours complet",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🔗 Lien du cours",
        value=f"[Accéder au cours]({course['link']})",
        inline=False
    )
    
    embed.set_footer(text="Cliquez sur 'Démarrer le QCM' après avoir lu le cours")
    
    view = CourseView(course, quiz_manager)
    await ctx.send(embed=embed, view=view)


@bot.command(name='check_exam_results')
@commands.has_permissions(administrator=True)
async def check_exam_results(ctx):
    """Vérifie et notifie les résultats d'examens web non notifiés (admin)"""
    try:
        await ctx.send("🔍 Vérification des résultats non notifiés...")
        
        unnotified = exam_db.get_unnotified_results(limit=50)
        
        if not unnotified:
            await ctx.send("✅ Aucun nouveau résultat à notifier")
            return
        
        await ctx.send(f"📊 {len(unnotified)} résultat(s) trouvé(s). Envoi en cours...")
        
        notified = 0
        for result in unnotified:
            try:
                user = await bot.fetch_user(result['user_id'])
                
                emoji = "✅" if result['passed'] else "❌"
                color = discord.Color.green() if result['passed'] else discord.Color.red()
                
                embed = discord.Embed(
                    title=f"{emoji} Résultat de votre examen web",
                    description=f"**{result['exam_title']}**",
                    color=color,
                    timestamp=datetime.fromisoformat(result['date'])
                )
                
                embed.add_field(
                    name="📊 Score",
                    value=f"{result['score']}/{result['total']} points",
                    inline=True
                )
                embed.add_field(
                    name="📈 Pourcentage",
                    value=f"{result['percentage']}%",
                    inline=True
                )
                embed.add_field(
                    name="✅ Seuil de réussite",
                    value=f"{result['passing_score']}%",
                    inline=True
                )
                
                if result['passed']:
                    embed.add_field(
                        name="🎉 Statut",
                        value="**RÉUSSI** - Félicitations !",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💪 Statut",
                        value="**Non validé** - Continuez vos efforts !",
                        inline=False
                    )
                
                embed.set_footer(text="Examen passé sur la plateforme web")
                
                await user.send(embed=embed)
                
                # Marquer comme notifié
                exam_db.mark_as_notified(
                    result['user_id'],
                    result['exam_id'],
                    result['date']
                )
                
                notified += 1
                
            except discord.Forbidden:
                print(f"Impossible d'envoyer MP à {result['user_id']}")
            except Exception as e:
                print(f"Erreur pour {result['user_id']}: {e}")
        
        await ctx.send(f"✅ {notified} notification(s) envoyée(s)")
    
    except Exception as e:
        await ctx.send(f"❌ Erreur générale: {str(e)}")
        print(f"Erreur check_exam_results: {e}")
        import traceback
        traceback.print_exc()


class CourseView(discord.ui.View):
    """Vue contenant le bouton pour démarrer le QCM"""
    def __init__(self, course, quiz_manager):
        super().__init__(timeout=None)
        self.course = course
        self.quiz_manager = quiz_manager
    
    @discord.ui.button(label="Démarrer le QCM", style=discord.ButtonStyle.primary, custom_id="start_quiz")
    async def start_quiz_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback du bouton - démarre le QCM en MP"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await interaction.user.send(f"🎓 Démarrage du QCM pour **{self.course['title']}**")
            await self.quiz_manager.start_quiz(interaction.user, self.course)
            await interaction.followup.send("✅ QCM envoyé en message privé !", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Impossible de vous envoyer un MP. Vérifiez vos paramètres de confidentialité.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)
            print(f"Erreur start_quiz_button: {e}")


# Gestion des erreurs de permissions
@send_course.error
async def send_course_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande")


# Lancement du bot
if __name__ == "__main__":
    try:
        bot.run(token=token)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
