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
# ===== INITIALISATION AUTOMATIQUE DE LA BASE DE DONNÉES =====
try:
    print("🔧 Vérification de la base de données...")
    from init_db import init_database
    init_database()
    print("✅ Base de données initialisée")
except Exception as e:
    print(f"⚠️ Erreur initialisation DB: {e}")
# =============================================================

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True
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

# Configuration des groupes
MAX_MEMBERS_PER_GROUP = 15
GROUP_COLORS = {
    1: discord.Color.blue(),
    2: discord.Color.green(),
    3: discord.Color.orange(),
    4: discord.Color.purple(),
    5: discord.Color.red()
}


class GroupManager:
    """Gestion des groupes et sous-groupes avec salons Discord"""
    
    def __init__(self, bot, cohort_manager):
        self.bot = bot
        self.cohort_manager = cohort_manager
    
    def get_subgroup_letter(self, count: int) -> str:
        """Retourne A, B, C... selon le nombre"""
        if count < MAX_MEMBERS_PER_GROUP:
            return ""
        
        subgroup_index = count // MAX_MEMBERS_PER_GROUP
        if subgroup_index == 0:
            return ""
        
        # A=1, B=2, C=3...
        return chr(64 + subgroup_index)  # 65 = A
    
    def format_group_name(self, level: int, subgroup: str = "") -> str:
        """Formate le nom du groupe (ex: Groupe 1, Groupe 1-A)"""
        if subgroup:
            return f"Groupe {level}-{subgroup}"
        return f"Groupe {level}"
    
    def format_channel_name(self, level: int, subgroup: str = "") -> str:
        """Formate le nom du salon (ex: groupe-1, groupe-1-a)"""
        if subgroup:
            return f"groupe-{level}-{subgroup.lower()}"
        return f"groupe-{level}"
    
    async def get_or_create_role(self, guild: discord.Guild, level: int, subgroup: str = "") -> discord.Role:
        """Récupère ou crée un rôle de groupe"""
        role_name = self.format_group_name(level, subgroup)
        
        # Chercher si le rôle existe
        role = discord.utils.get(guild.roles, name=role_name)
        
        if not role:
            # Créer le rôle
            color = GROUP_COLORS.get(level, discord.Color.default())
            role = await guild.create_role(
                name=role_name,
                color=color,
                mentionable=True,
                reason="Création automatique du groupe"
            )
            print(f"✅ Rôle créé : {role_name}")
        
        return role
    
    async def get_or_create_channel(self, guild: discord.Guild, level: int, subgroup: str, role: discord.Role) -> discord.TextChannel:
        """Récupère ou crée un salon privé pour un groupe"""
        channel_name = self.format_channel_name(level, subgroup)
        
        # Chercher si le salon existe
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not channel:
            # Chercher ou créer la catégorie "Groupes de Formation"
            category = discord.utils.get(guild.categories, name="📚 Groupes de Formation")
            
            if not category:
                category = await guild.create_category(
                    "📚 Groupes de Formation",
                    reason="Catégorie pour les groupes"
                )
            
            # Permissions : Visible uniquement pour le rôle
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    add_reactions=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
            
            # Créer le salon
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Salon privé pour le {self.format_group_name(level, subgroup)}",
                reason="Création automatique du salon de groupe"
            )
            
            # Message de bienvenue dans le salon
            embed = discord.Embed(
                title=f"🎓 Bienvenue dans le {self.format_group_name(level, subgroup)} !",
                description=(
                    f"Ce salon est réservé aux membres du {self.format_group_name(level, subgroup)}.\n\n"
                    "**Règles** :\n"
                    "• Entraide et respect mutuel\n"
                    "• Posez vos questions ici\n"
                    "• Les cours seront annoncés dans ce salon\n\n"
                    "**Pour accéder aux examens** :\n"
                    "👉 Rendez-vous sur le site web avec votre ID Discord"
                ),
                color=GROUP_COLORS.get(level, discord.Color.blue())
            )
            await channel.send(embed=embed)
            
            print(f"✅ Salon créé : #{channel_name}")
        
        return channel
    
    async def count_members_in_level(self, guild: discord.Guild, level: int) -> dict:
        """Compte les membres par sous-groupe dans un niveau"""
        counts = {}
        
        # Chercher tous les rôles du niveau (Groupe X, Groupe X-A, etc.)
        for role in guild.roles:
            if role.name.startswith(f"Groupe {level}"):
                subgroup = ""
                if "-" in role.name:
                    subgroup = role.name.split("-")[1]
                counts[subgroup] = len(role.members)
        
        return counts
    
    async def assign_member_to_group(self, member: discord.Member, level: int) -> tuple:
        """Assigne un membre à un groupe (avec gestion des sous-groupes)"""
        guild = member.guild
        
        # Compter les membres actuels dans ce niveau
        counts = await self.count_members_in_level(guild, level)
        
        # Déterminer le sous-groupe
        subgroup = ""
        if counts.get("", 0) >= MAX_MEMBERS_PER_GROUP:
            # Groupe principal plein, chercher un sous-groupe
            subgroup_letter = "A"
            while counts.get(subgroup_letter, 0) >= MAX_MEMBERS_PER_GROUP:
                subgroup_letter = chr(ord(subgroup_letter) + 1)
            subgroup = subgroup_letter
        
        # Créer ou récupérer le rôle et le salon
        role = await self.get_or_create_role(guild, level, subgroup)
        channel = await self.get_or_create_channel(guild, level, subgroup, role)
        
        # Assigner le rôle au membre
        await member.add_roles(role, reason="Attribution automatique du groupe")
        
        return role, channel, subgroup
    
    async def promote_member(self, member: discord.Member, old_level: int, new_level: int):
        """Promeut un membre vers un niveau supérieur"""
        guild = member.guild
        
        # Retirer tous les anciens rôles de groupe
        old_roles = [r for r in member.roles if r.name.startswith("Groupe")]
        if old_roles:
            await member.remove_roles(*old_roles, reason="Promotion vers niveau supérieur")
        
        # Assigner le nouveau groupe
        new_role, new_channel, subgroup = await self.assign_member_to_group(member, new_level)
        
        # Message de félicitations en MP
        try:
            embed = discord.Embed(
                title="🎉 Félicitations !",
                description=(
                    f"Vous avez réussi l'examen du niveau {old_level} !\n\n"
                    f"**Vous êtes maintenant dans le {self.format_group_name(new_level, subgroup)}** 🚀\n\n"
                    f"Accédez à votre nouveau salon : {new_channel.mention}\n"
                    "Continuez comme ça ! 💪"
                ),
                color=discord.Color.gold()
            )
            await member.send(embed=embed)
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name}")
        
        # Annonce dans le nouveau salon
        embed = discord.Embed(
            title="👋 Nouveau Membre !",
            description=f"{member.mention} vient de rejoindre le groupe ! Bienvenue ! 🎉",
            color=GROUP_COLORS.get(new_level, discord.Color.green())
        )
        await new_channel.send(embed=embed)


# Initialisation du GroupManager
group_manager = GroupManager(bot, cohort_manager)


class BotHTTPServer:
    """Serveur HTTP pour recevoir les requêtes du site web"""
    def __init__(self, bot, quiz_manager, config, exam_db, group_manager):
        self.bot = bot
        self.quiz_manager = quiz_manager
        self.config = config
        self.exam_db = exam_db
        self.group_manager = group_manager
        self.app = web.Application()
        self.app.router.add_post('/api/send_quiz', self.handle_send_quiz)
        self.app.router.add_post('/api/mark_notified', self.handle_mark_notified)
        self.app.router.add_post('/api/promote_user', self.handle_promote_user)
        self.runner = None

    async def handle_send_quiz(self, request):
        """Envoie un quiz à un utilisateur"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            course_id = data.get('course_id')
            
            course = next((c for c in self.config['courses'] if c['id'] == course_id), None)
            
            if not course:
                return web.json_response({
                    'success': False,
                    'error': 'Course not found'
                }, status=404)
            
            user = await self.bot.fetch_user(user_id)
            
            if not user:
                return web.json_response({
                    'success': False,
                    'error': 'User not found'
                }, status=404)
            
            await self.quiz_manager.send_quiz(user, course)
            
            return web.json_response({'success': True})
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
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
    
    async def handle_promote_user(self, request):
        """Promeut un utilisateur après réussite d'examen"""
        try:
            data = await request.json()
            user_id = data.get('user_id')
            old_level = data.get('old_level')
            new_level = data.get('new_level')
            
            # Trouver le membre dans toutes les guildes
            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    await self.group_manager.promote_member(member, old_level, new_level)
                    break
            
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
http_server = BotHTTPServer(bot, quiz_manager, config, exam_db, group_manager)


@bot.event
async def on_ready():
    print(f'✅ Bot connecté en tant que {bot.user}')
    
    # Démarrer le scheduler
    scheduler.start()
    
    # Démarrer le serveur HTTP
    await http_server.start()
    
    print(f'📊 Guildes : {len(bot.guilds)}')


@bot.event
async def on_member_join(member: discord.Member):
    """Événement quand un nouveau membre rejoint le serveur"""
    print(f"👋 Nouveau membre : {member.name}")
    
    try:
        # 1. Créer l'utilisateur dans la base de données (Groupe 1 par défaut)
        user_info = cohort_manager.create_user(member.id, member.name)
        
        # 2. Assigner au Groupe 1 avec gestion automatique des sous-groupes
        role, channel, subgroup = await group_manager.assign_member_to_group(member, 1)
        
        # 3. Message de bienvenue en MP
        embed = discord.Embed(
            title="🎓 Bienvenue dans la Formation Python !",
            description=(
                f"Bonjour {member.mention} ! 👋\n\n"
                f"**Vous avez été assigné au {group_manager.format_group_name(1, subgroup)}**\n\n"
                "**Comment ça marche ?**\n"
                f"• Votre salon privé : {channel.mention}\n"
                "• Les cours seront annoncés dans votre salon\n"
                "• Passez les examens sur le site web avec votre ID Discord\n"
                f"• Votre ID Discord : `{member.id}`\n\n"
                "**Pour progresser** :\n"
                "1. Suivez les cours dans votre salon\n"
                "2. Passez les QCM Discord après chaque cours\n"
                "3. Réussissez l'examen web pour passer au Groupe 2\n\n"
                "Bonne formation ! 🚀"
            ),
            color=discord.Color.blue()
        )
        
        await member.send(embed=embed)
        
        # 4. Annonce dans le salon du groupe
        welcome_embed = discord.Embed(
            title="👋 Nouveau Membre !",
            description=f"{member.mention} vient de rejoindre le {group_manager.format_group_name(1, subgroup)} ! Bienvenue ! 🎉",
            color=discord.Color.green()
        )
        await channel.send(embed=welcome_embed)
        
        print(f"✅ {member.name} assigné au {group_manager.format_group_name(1, subgroup)}")
        
    except discord.Forbidden:
        print(f"⚠️ Impossible d'envoyer un MP à {member.name}")
    except Exception as e:
        print(f"❌ Erreur lors de l'onboarding de {member.name}: {e}")


class CourseView(discord.ui.View):
    """Bouton pour démarrer un QCM"""
    def __init__(self, course, quiz_manager):
        super().__init__(timeout=None)
        self.course = course
        self.quiz_manager = quiz_manager
    
    @discord.ui.button(label="Démarrer le QCM", style=discord.ButtonStyle.primary, emoji="📝")
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.quiz_manager.send_quiz(interaction.user, self.course)
            await interaction.followup.send(
                "✅ Le QCM vous a été envoyé en message privé !",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je ne peux pas vous envoyer de message privé. Vérifiez vos paramètres de confidentialité.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur : {str(e)}",
                ephemeral=True
            )


@bot.command(name='send_course')
@commands.has_permissions(administrator=True)
async def send_course(ctx, course_number: int, target_group: str = None):
    """
    Envoie un cours stylé via embed (admin uniquement)
    
    Usage:
    /send_course 1                    -> Envoie à tous les groupes
    /send_course 1 1                  -> Envoie uniquement au Groupe 1
    /send_course 1 1-A                -> Envoie uniquement au Groupe 1-A
    """
    
    course = next((c for c in config['courses'] if c['id'] == course_number), None)
    
    if not course:
        await ctx.send(f"❌ Cours {course_number} introuvable")
        return
    
    # Créer l'embed stylé
    embed = discord.Embed(
        title=f"📚 {course['title']}",
        description="Un nouveau cours est disponible ! Cliquez sur le lien pour y accéder.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🔗 Lien du cours",
        value=f"[Accéder au cours complet]({course['link']})",
        inline=False
    )
    
    embed.set_footer(text="Cliquez sur 'Démarrer le QCM' après avoir lu le cours")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2232/2232688.png")  # Icône livre
    
    view = CourseView(course, quiz_manager)
    
    # Déterminer où envoyer
    if target_group:
        # Envoyer à un groupe spécifique
        channel_name = f"groupe-{target_group.lower()}"
        channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        
        if not channel:
            await ctx.send(f"❌ Salon #{channel_name} introuvable")
            return
        
        await channel.send(embed=embed, view=view)
        await ctx.send(f"✅ Cours envoyé dans #{channel_name}")
    else:
        # Envoyer à tous les groupes
        category = discord.utils.get(ctx.guild.categories, name="📚 Groupes de Formation")
        
        if not category:
            await ctx.send("❌ Aucun groupe trouvé. Les groupes seront créés automatiquement quand des membres rejoindront.")
            return
        
        sent_count = 0
        for channel in category.text_channels:
            if channel.name.startswith("groupe-"):
                await channel.send(embed=embed, view=view)
                sent_count += 1
        
        await ctx.send(f"✅ Cours envoyé dans {sent_count} salon(s) de groupe")


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
        promoted = 0
        
        for result in unnotified:
            try:
                user = await bot.fetch_user(result['user_id'])
                
                emoji = "✅" if result['passed'] else "❌"
                color = discord.Color.green() if result['passed'] else discord.Color.red()
                
                embed = discord.Embed(
                    title=f"{emoji} Résultat de l'examen",
                    description=f"**{result['exam_title']}**",
                    color=color
                )
                
                embed.add_field(name="Score", value=f"{result['score']}/{result['total']}", inline=True)
                embed.add_field(name="Pourcentage", value=f"{result['percentage']:.1f}%", inline=True)
                embed.add_field(name="Seuil de réussite", value=f"{result['passing_score']}%", inline=True)
                
                if result['passed']:
                    embed.add_field(
                        name="🎉 Félicitations !",
                        value="Vous avez réussi l'examen ! Vous allez être promu au niveau supérieur.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="💪 Continuez !",
                        value="Révisez le cours et retentez l'examen.",
                        inline=False
                    )
                
                embed.set_footer(text=f"Examen passé le {result['date']}")
                
                await user.send(embed=embed)
                notified += 1
                
                # Marquer comme notifié
                exam_db.mark_as_notified(result['user_id'], result['exam_id'], result['date'])
                
                # Si réussi, promouvoir l'utilisateur
                if result['passed']:
                    member = ctx.guild.get_member(result['user_id'])
                    if member:
                        user_info = cohort_manager.get_user_info(result['user_id'])
                        old_level = user_info['niveau_actuel']
                        new_level = old_level + 1
                        
                        # Mettre à jour le niveau dans la BDD
                        cohort_manager.update_user_level(result['user_id'], new_level)
                        
                        # Promouvoir sur Discord
                        await group_manager.promote_member(member, old_level, new_level)
                        promoted += 1
                
            except discord.Forbidden:
                print(f"⚠️ Impossible d'envoyer un MP à l'utilisateur {result['user_id']}")
            except Exception as e:
                print(f"❌ Erreur pour l'utilisateur {result['user_id']}: {e}")
        
        await ctx.send(
            f"✅ Notifications envoyées : {notified}/{len(unnotified)}\n"
            f"🚀 Promotions effectuées : {promoted}"
        )
        
    except Exception as e:
        await ctx.send(f"❌ Erreur : {str(e)}")


@bot.command(name='group_stats')
@commands.has_permissions(administrator=True)
async def group_stats(ctx):
    """Affiche les statistiques des groupes (admin)"""
    try:
        embed = discord.Embed(
            title="📊 Statistiques des Groupes",
            color=discord.Color.blue()
        )
        
        category = discord.utils.get(ctx.guild.categories, name="📚 Groupes de Formation")
        
        if not category:
            await ctx.send("❌ Aucun groupe créé pour le moment")
            return
        
        total_members = 0
        
        for level in range(1, 6):  # Groupes 1 à 5
            counts = await group_manager.count_members_in_level(ctx.guild, level)
            
            if counts:
                level_total = sum(counts.values())
                total_members += level_total
                
                details = []
                for subgroup, count in sorted(counts.items()):
                    group_name = group_manager.format_group_name(level, subgroup)
                    details.append(f"• {group_name}: {count} membre(s)")
                
                embed.add_field(
                    name=f"Niveau {level} ({level_total} membres)",
                    value="\n".join(details) if details else "Aucun membre",
                    inline=False
                )
        
        embed.set_footer(text=f"Total : {total_members} membre(s) en formation")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Erreur : {str(e)}")


# Lancement du bot
if __name__ == '__main__':
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Erreur critique : {e}")
