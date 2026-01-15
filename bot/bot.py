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
from role_channel_manager import RoleChannelManager

keep_alive()
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Chargement de la config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Initialisation des managers (PostgreSQL)
cohort_manager = CohortManagerSQL()
review_db = ReviewDatabaseSQL()
exam_db = ExamResultDatabaseSQL()
role_manager = RoleChannelManager(bot)
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
    
    # Synchroniser les rôles et salons existants
    for guild in bot.guilds:
        await role_manager.sync_existing_cohorts(guild)
    
    print(f'📊 Guildes : {len(bot.guilds)}')


@bot.event
async def on_member_join(member):
    """Quand un nouveau membre rejoint le serveur"""
    try:
        # Vérifier si l'utilisateur existe déjà dans la base
        user_info = cohort_manager.get_user_info(member.id)
        
        if user_info:
            # L'utilisateur revient : lui redonner son rôle
            cohort_info = cohort_manager.get_cohort_info(user_info['cohorte_id'])
            if cohort_info and cohort_info.get('role_id'):
                role = member.guild.get_role(cohort_info['role_id'])
                if role:
                    await member.add_roles(role)
                    print(f"✅ Rôle {role.name} réattribué à {member.name}")
        
    except Exception as e:
        print(f"Erreur on_member_join: {e}")


@bot.command(name='send_course')
@commands.has_permissions(administrator=True)
async def send_course(ctx, course_number: int, member: discord.Member = None):
    """
    ADMIN UNIQUEMENT: Envoie un cours en MP
    Usage: /send_course 1 @membre
    """
    
    course = next((c for c in config['courses'] if c['id'] == course_number), None)
    
    if not course:
        await ctx.send(f"❌ Cours {course_number} introuvable")
        return
    
    if member is None:
        await ctx.send("❌ Vous devez mentionner un utilisateur : `/send_course 1 @membre`")
        return
    
    try:
        # Envoyer le cours en MP
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
        
        embed.set_footer(text="Étudiez bien le cours avant votre examen")
        
        await member.send(embed=embed)
        
        # Confirmation dans le salon
        await ctx.send(f"✅ Cours {course_number} envoyé en MP à {member.mention}")
        
    except discord.Forbidden:
        await ctx.send(f"❌ Impossible d'envoyer un MP à {member.mention}")
    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur send_course: {e}")
        import traceback
        traceback.print_exc()


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
                    title=f"{emoji} Résultat de votre examen",
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
                        value="**RÉUSSI** - Vous passez au niveau suivant !",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💪 Statut",
                        value="**Non validé** - Vous restez dans votre groupe actuel",
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
                
                # Si réussi, mettre à jour le rôle Discord
                if result['passed']:
                    user_info = cohort_manager.get_user_info(result['user_id'])
                    if user_info:
                        for guild in bot.guilds:
                            member = guild.get_member(result['user_id'])
                            if member:
                                # Retirer l'ancien rôle et ajouter le nouveau
                                await role_manager.update_member_role(
                                    guild, 
                                    member, 
                                    user_info['niveau_actuel']
                                )
                                break
                
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


@bot.command(name='sync_roles')
@commands.has_permissions(administrator=True)
async def sync_roles(ctx):
    """Synchronise tous les rôles et salons avec la base de données"""
    await ctx.send("🔄 Synchronisation en cours...")
    await role_manager.sync_existing_cohorts(ctx.guild)
    await ctx.send("✅ Synchronisation terminée !")


@bot.command(name='my_group')
async def my_group(ctx):
    """Affiche les informations de groupe de l'utilisateur"""
    user_info = cohort_manager.get_user_info(ctx.author.id)
    
    if not user_info:
        await ctx.send("❌ Vous n'êtes pas encore inscrit. Contactez un administrateur.")
        return
    
    cohort_info = cohort_manager.get_cohort_info(user_info['cohorte_id'])
    next_exam = cohort_manager.get_next_exam_for_user(ctx.author.id)
    
    embed = discord.Embed(
        title="📋 Vos informations",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎓 Cohorte",
        value=user_info['cohorte_id'],
        inline=True
    )
    embed.add_field(
        name="📊 Niveau actuel",
        value=str(user_info['niveau_actuel']),
        inline=True
    )
    embed.add_field(
        name="✅ Examens réussis",
        value=str(user_info['examens_reussis']),
        inline=True
    )
    
    if next_exam:
        exam_date = datetime.fromisoformat(next_exam['date'])
        embed.add_field(
            name="📅 Prochain examen",
            value=f"Niveau {next_exam['niveau']}\n{exam_date.strftime('%d/%m/%Y à %H:%M')}",
            inline=False
        )
    
    await ctx.send(embed=embed)


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
