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

# ✅ UTILISATION DE POSTGRESQL avec nouveaux managers
from cohorte_manager_sql import CohortManagerSQL
from database_sql import ReviewDatabaseSQL
from exam_result_database_sql import ExamResultDatabaseSQL
from discord_group_manager import DiscordGroupManager

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))  # Votre ID Discord

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Chargement de la config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Chargement des examens
with open('exam.json', 'r', encoding='utf-8') as f:
    exams_data = json.load(f)

# Initialisation des managers (PostgreSQL)
cohort_manager = CohortManagerSQL()
review_db = ReviewDatabaseSQL()
exam_db = ExamResultDatabaseSQL()
quiz_manager = QuizManager(bot, review_db, config)
scheduler = ReviewScheduler(bot, review_db, quiz_manager)

# Le DiscordGroupManager sera initialisé après le démarrage du bot
discord_group_manager = None


class BotHTTPServer:
    """Serveur HTTP pour recevoir les requêtes du site web"""

    def __init__(self, bot, quiz_manager, config, exam_db, cohort_manager):
        self.bot = bot
        self.quiz_manager = quiz_manager
        self.config = config
        self.exam_db = exam_db
        self.cohort_manager = cohort_manager
        self.app = web.Application()
        self.app.router.add_post('/api/send_quiz', self.handle_send_quiz)
        self.app.router.add_post('/api/mark_notified', self.handle_mark_notified)
        self.app.router.add_post('/api/submit_exam', self.handle_submit_exam)
        self.runner = None

    async def handle_send_quiz(self, request):
        """Endpoint pour envoyer un quiz en MP (RÉSERVÉ À L'ADMIN)"""
        try:
            data = await request.json()
            requester_id = int(data.get('requester_id', 0))

            # Vérifier que c'est l'admin
            if requester_id != ADMIN_USER_ID:
                return web.json_response({
                    'success': False,
                    'message': '❌ Cette fonction est réservée à l\'administrateur'
                }, status=403)

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
            print(f"❌ Erreur handle_send_quiz: {e}")
            return web.json_response({
                'success': False,
                'message': str(e)
            }, status=500)

    async def handle_submit_exam(self, request):
        """Gère la soumission d'un examen depuis le site web"""
        try:
            data = await request.json()
            user_id = int(data['user_id'])
            exam_id = int(data['exam_id'])
            passed = bool(data['passed'])

            # Enregistrer le résultat
            self.exam_db.save_exam_result(data)

            # Mettre à jour le niveau de l'utilisateur
            message, nouveau_niveau, nouveau_sous_groupe = self.cohort_manager.update_user_after_exam(
                user_id, passed
            )

            # Si réussite, mettre à jour le rôle Discord
            if passed and discord_group_manager:
                try:
                    guild = self.bot.guilds[0] if self.bot.guilds else None
                    if guild:
                        member = guild.get_member(user_id)
                        if member:
                            # Créer ou récupérer le groupe Discord
                            role_id, channel_id, sous_groupe = await discord_group_manager.get_or_create_group(
                                nouveau_niveau, user_id
                            )

                            # Assigner l'utilisateur au nouveau groupe
                            await discord_group_manager.assign_user_to_group(
                                member, nouveau_niveau, nouveau_sous_groupe, role_id
                            )

                            # Mettre à jour la base de données
                            self.cohort_manager.update_user_discord_info(user_id, role_id, channel_id)
                except Exception as e:
                    print(f"⚠️ Erreur mise à jour Discord: {e}")

            return web.json_response({
                'success': True,
                'message': message,
                'niveau': nouveau_niveau,
                'sous_groupe': nouveau_sous_groupe
            })

        except Exception as e:
            print(f"❌ Erreur handle_submit_exam: {e}")
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
http_server = BotHTTPServer(bot, quiz_manager, config, exam_db, cohort_manager)


@bot.event
async def on_ready():
    global discord_group_manager

    print(f'✅ Bot connecté en tant que {bot.user}')
    print(f'📊 Guildes : {len(bot.guilds)}')

    # Initialiser le gestionnaire de groupes Discord
    if bot.guilds:
        discord_group_manager = DiscordGroupManager(bot.guilds[0])
        print(f"✅ DiscordGroupManager initialisé pour {bot.guilds[0].name}")

    # Démarrer le scheduler
    scheduler.start()

    # Démarrer le serveur HTTP
    await http_server.start()


@bot.event
async def on_member_join(member: discord.Member):
    """Gère l'arrivée d'un nouveau membre"""
    try:
        # Ajouter l'utilisateur à une cohorte
        cohorte_id, niveau, sous_groupe = cohort_manager.add_user_to_cohort(
            member.id, member.name
        )

        # Créer ou récupérer le groupe Discord
        if discord_group_manager:
            role_id, channel_id, sous_groupe = await discord_group_manager.get_or_create_group(
                niveau, member.id
            )

            # Assigner le rôle au membre
            await discord_group_manager.assign_user_to_group(
                member, niveau, sous_groupe, role_id
            )

            # Mettre à jour la base de données
            cohort_manager.update_user_discord_info(member.id, role_id, channel_id)

        # Message de bienvenue en MP
        embed = discord.Embed(
            title="🎓 Bienvenue dans la formation !",
            description=f"Vous avez été assigné au **Groupe {niveau}{sous_groupe}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📚 Votre cohorte",
            value=f"Cohorte: {cohorte_id}",
            inline=False
        )
        embed.add_field(
            name="🎯 Prochaine étape",
            value="Consultez votre salon de groupe pour accéder aux cours et préparer votre examen",
            inline=False
        )

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer MP à {member.name}")

        print(f"✅ {member.name} inscrit dans Groupe-{niveau}{sous_groupe}")

    except Exception as e:
        print(f"❌ Erreur on_member_join: {e}")


@bot.command(name='send_course')
async def send_course(ctx, user_id: int):
    """
    Envoie le cours à un utilisateur selon son niveau (RÉSERVÉ À L'ADMIN)
    Usage: /send_course <user_id>
    """
    # Vérifier que c'est l'admin
    if ctx.author.id != ADMIN_USER_ID:
        await ctx.send("❌ Cette commande est réservée à l'administrateur")
        return

    try:
        # Récupérer les informations de l'utilisateur
        user_info = cohort_manager.get_user_info(user_id)

        if not user_info:
            await ctx.send(f"❌ Utilisateur {user_id} non trouvé dans la base de données")
            return

        niveau = user_info['niveau_actuel']
        sous_groupe = user_info['sous_groupe']

        # Récupérer le cours correspondant au niveau
        course = next((c for c in config['courses'] if c['id'] == niveau), None)

        if not course:
            await ctx.send(f"❌ Aucun cours trouvé pour le niveau {niveau}")
            return

        # Récupérer l'utilisateur Discord
        user = await bot.fetch_user(user_id)

        # Créer l'embed du cours
        embed = discord.Embed(
            title=f"📚 {course['title']}",
            description=f"Cours pour le niveau {niveau} - Groupe {niveau}{sous_groupe}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔗 Lien du cours",
            value=f"[Accéder au cours]({course['link']})",
            inline=False
        )
        embed.set_footer(text="Étudiez bien avant de passer votre examen")

        # Envoyer le cours en MP
        await user.send(embed=embed)
        await ctx.send(f"✅ Cours niveau {niveau} envoyé à {user.name}")

    except discord.Forbidden:
        await ctx.send(f"❌ Impossible d'envoyer un MP à cet utilisateur (MPs bloqués)")
    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur send_course: {e}")


@bot.command(name='mon_info')
async def mon_info(ctx):
    """Affiche vos informations de formation"""
    try:
        user_info = cohort_manager.get_user_info(ctx.author.id)

        if not user_info:
            await ctx.send("❌ Vous n'êtes pas encore inscrit à la formation")
            return

        # Récupérer le prochain examen
        next_exam = cohort_manager.get_next_exam_for_user(ctx.author.id)

        embed = discord.Embed(
            title="📊 Vos informations de formation",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="👤 Utilisateur",
            value=user_info['username'],
            inline=True
        )
        embed.add_field(
            name="🎯 Groupe",
            value=f"Niveau {user_info['niveau_actuel']}{user_info['sous_groupe']}",
            inline=True
        )
        embed.add_field(
            name="🏆 Examens réussis",
            value=str(user_info['examens_reussis']),
            inline=True
        )
        embed.add_field(
            name="📅 Cohorte",
            value=user_info['cohorte_id'],
            inline=True
        )

        if next_exam:
            date_debut = datetime.fromisoformat(next_exam['date_debut'])
            date_fin = datetime.fromisoformat(next_exam['date_fin'])
            embed.add_field(
                name="📝 Prochain examen",
                value=f"Niveau {next_exam['niveau']}\n"
                      f"Du {date_debut.strftime('%d/%m/%Y %H:%M')}\n"
                      f"Au {date_fin.strftime('%d/%m/%Y %H:%M')}",
                inline=False
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur mon_info: {e}")


@bot.command(name='passer_examen')
async def passer_examen(ctx):
    """Vérifie si vous pouvez passer l'examen et vous redirige vers le site web"""
    try:
        user_info = cohort_manager.get_user_info(ctx.author.id)

        if not user_info:
            await ctx.send("❌ Vous n'êtes pas inscrit à la formation")
            return

        next_exam = cohort_manager.get_next_exam_for_user(ctx.author.id)

        if not next_exam:
            await ctx.send("❌ Aucun examen disponible")
            return

        date_debut = datetime.fromisoformat(next_exam['date_debut'])
        date_fin = datetime.fromisoformat(next_exam['date_fin'])
        now = datetime.now()

        # Vérifier si dans la tranche horaire
        if now < date_debut:
            await ctx.send(
                f"⏰ L'examen n'est pas encore disponible.\n"
                f"Début: {date_debut.strftime('%d/%m/%Y à %H:%M')}\n"
                f"Fin: {date_fin.strftime('%d/%m/%Y à %H:%M')}"
            )
            return

        if now > date_fin:
            await ctx.send(
                f"❌ La période d'examen est terminée.\n"
                f"L'examen était disponible jusqu'au {date_fin.strftime('%d/%m/%Y à %H:%M')}"
            )
            return

        # L'examen est disponible
        embed = discord.Embed(
            title="✅ Examen disponible !",
            description=f"Vous pouvez passer l'examen de niveau {next_exam['niveau']}",
            color=discord.Color.green()
        )
        embed.add_field(
            name="⏱️ Temps restant",
            value=f"Jusqu'au {date_fin.strftime('%d/%m/%Y à %H:%M')}",
            inline=False
        )
        embed.add_field(
            name="🔗 Passer l'examen",
            value=f"[Cliquez ici pour passer l'examen](https://site-fromation.onrender.com/exams)",
            inline=False
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur passer_examen: {e}")


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
                        value="**RÉUSSI** - Félicitations ! Vous passez au niveau suivant.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💪 Statut",
                        value="**Non validé** - Continuez vos efforts ! Vous repasserez l'examen.",
                        inline=False
                    )

                await user.send(embed=embed)

                exam_db.mark_as_notified(
                    result['user_id'],
                    result['exam_id'],
                    result['date']
                )

                notified += 1

            except discord.Forbidden:
                print(f"⚠️ Impossible d'envoyer MP à {result['user_id']}")
            except Exception as e:
                print(f"❌ Erreur pour {result['user_id']}: {e}")

        await ctx.send(f"✅ {notified} notification(s) envoyée(s)")

    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur check_exam_results: {e}")


@bot.command(name='liste_groupes')
@commands.has_permissions(administrator=True)
async def liste_groupes(ctx):
    """Affiche la liste de tous les groupes Discord (admin)"""
    try:
        if not discord_group_manager:
            await ctx.send("❌ DiscordGroupManager non initialisé")
            return

        groups = discord_group_manager.get_all_groups()

        if not groups:
            await ctx.send("📊 Aucun groupe créé pour le moment")
            return

        embed = discord.Embed(
            title="📊 Liste des groupes Discord",
            color=discord.Color.blue()
        )

        for group in groups:
            embed.add_field(
                name=f"Groupe {group['niveau']}{group['sous_groupe']}",
                value=f"👥 Membres: {group['membres_count']}/{group['max_membres']}\n"
                      f"📝 Rôle: <@&{group['role_id']}>\n"
                      f"💬 Salon: <#{group['channel_id']}>",
                inline=True
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Erreur: {str(e)}")
        print(f"Erreur liste_groupes: {e}")


# Gestion des erreurs de permissions
@send_course.error
async def send_course_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande")


@check_exam_results.error
async def check_exam_results_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande")


# Lancement du bot
if __name__ == "__main__":
    try:
        bot.run(token=token)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
