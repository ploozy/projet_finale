"""
Bot Discord - Version Ultime
✅ Onboarding automatique
✅ Notifications automatiques des résultats d'examens (toutes les 30s)
✅ Sync automatique des rôles Discord
"""

import discord
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

# Keep-alive
from stay_alive import keep_alive
keep_alive()
load_dotenv()

# ===== INITIALISATION BASE DE DONNÉES =====
print("🔧 Initialisation de la base de données...")
try:
    from db_connection import engine, Base, SessionLocal
    from models import Cohorte, Utilisateur, ExamResult
    from sqlalchemy import text
    
    Base.metadata.create_all(engine)
    print("✅ Tables créées")
    
    # Ajouter colonne 'groupe' si nécessaire
    db = SessionLocal()
    try:
        check = text("SELECT column_name FROM information_schema.columns WHERE table_name='utilisateurs' AND column_name='groupe'")
        if not db.execute(check).fetchone():
            db.execute(text("ALTER TABLE utilisateurs ADD COLUMN groupe VARCHAR(10) DEFAULT '1-A'"))
            db.commit()
            print("✅ Colonne 'groupe' ajoutée")
    except:
        pass
    finally:
        db.close()
    
    print("✅ Base de données prête")
    
except Exception as e:
    print(f"⚠️ Erreur DB: {e}")

print("=" * 50)

# Configuration du bot
token = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Variable globale pour stocker le serveur principal
main_guild = None


@bot.event
async def on_ready():
    """Appelé quand le bot est connecté"""
    global main_guild
    
    print(f'✅ Bot connecté : {bot.user}')
    print(f'📊 Serveurs : {len(bot.guilds)}')
    
    if bot.guilds:
        main_guild = bot.guilds[0]
        print(f'🏠 Serveur principal : {main_guild.name}')
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ Commandes synchronisées : {len(synced)}')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')
    
    # Démarrer la tâche de vérification automatique
    if not check_results_task.is_running():
        check_results_task.start()
        print("✅ Tâche de vérification automatique démarrée (toutes les 30s)")


@tasks.loop(seconds=30)
async def check_results_task():
    """
    TÂCHE AUTOMATIQUE - S'exécute toutes les 30 secondes
    Vérifie s'il y a de nouveaux résultats d'examens
    Et notifie automatiquement les utilisateurs
    """
    global main_guild
    
    if not main_guild:
        return
    
    from db_connection import SessionLocal
    from models import ExamResult, Utilisateur
    
    db = SessionLocal()
    
    try:
        # Récupérer les résultats non notifiés
        results = db.query(ExamResult).filter(ExamResult.notified == False).all()
        
        if not results:
            return  # Rien à faire
        
        print(f"\n{'='*50}")
        print(f"🔔 AUTO-CHECK : {len(results)} nouveaux résultats")
        
        for result in results:
            try:
                # Récupérer l'utilisateur en DB
                user_db = db.query(Utilisateur).filter(
                    Utilisateur.user_id == result.user_id
                ).first()
                
                if not user_db:
                    print(f"⚠️ User {result.user_id} pas en DB")
                    continue
                
                # Récupérer le membre Discord
                member = main_guild.get_member(result.user_id)
                
                if not member:
                    print(f"⚠️ Member {result.user_id} pas sur Discord")
                    continue
                
                # Trouver l'ancien groupe en regardant les rôles Discord actuels
                old_groupe = None
                for role in member.roles:
                    if role.name.startswith("Groupe "):
                        old_groupe = role.name.replace("Groupe ", "")
                        break
                
                if not old_groupe:
                    old_groupe = "1-A"
                
                new_groupe = user_db.groupe
                
                print(f"🔍 {member.name}")
                print(f"   Ancien: {old_groupe} | Nouveau: {new_groupe}")
                
                # SI RÉUSSI ET CHANGEMENT DE GROUPE → Changer les rôles
                if result.passed and old_groupe != new_groupe:
                    print(f"🎉 PROMOTION : {old_groupe} → {new_groupe}")
                    
                    # Retirer TOUS les anciens rôles "Groupe X"
                    roles_to_remove = [r for r in member.roles if r.name.startswith("Groupe ")]
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                        print(f"   ❌ Rôles retirés : {[r.name for r in roles_to_remove]}")
                    
                    # Ajouter le nouveau rôle (ou le créer)
                    new_role = discord.utils.get(main_guild.roles, name=f"Groupe {new_groupe}")
                    if not new_role:
                        new_role = await main_guild.create_role(
                            name=f"Groupe {new_groupe}",
                            color=discord.Color.blue(),
                            mentionable=True
                        )
                        print(f"   ✅ Rôle créé : {new_role.name}")
                    
                    await member.add_roles(new_role)
                    print(f"   ✅ Rôle ajouté : {new_role.name}")
                    
                    # Créer les salons si nécessaire
                    await create_group_channels(main_guild, new_groupe, new_role)
                    
                    # Envoyer les cours du nouveau niveau dans le salon ressources
                    await on_user_level_change(user_db.user_id, user_db.niveau_actuel, main_guild)
                    print(f"   📚 Ressources envoyées pour niveau {user_db.niveau_actuel}")
                
                # Message en MP
                if result.passed:
                    message = (
                        f"🎉 **Félicitations {member.mention} !**\n\n"
                        f"Tu as **réussi** l'examen **{result.exam_title}** !\n\n"
                        f"📊 **Score** : {result.percentage}% ({result.score}/{result.total})\n"
                        f"✅ **Seuil** : {result.passing_score}%\n\n"
                        f"🎊 **Tu as été promu !**\n"
                        f"**Ancien groupe** : {old_groupe}\n"
                        f"**Nouveau groupe** : {new_groupe}\n"
                        f"**Nouveau niveau** : {user_db.niveau_actuel}\n\n"
                        f"Continue comme ça ! 💪"
                    )
                else:
                    message = (
                        f"📝 **Résultat de ton examen**\n\n"
                        f"Examen : **{result.exam_title}**\n\n"
                        f"📊 **Score** : {result.percentage}% ({result.score}/{result.total})\n"
                        f"❌ **Seuil requis** : {result.passing_score}%\n\n"
                        f"Tu n'as pas atteint le seuil cette fois.\n"
                        f"Révise et retente quand tu es prêt(e) !\n"
                        f"Tu peux le faire ! 💪"
                    )
                
                try:
                    await member.send(message)
                    print(f"✅ Notification envoyée à {member.name}")
                except discord.Forbidden:
                    print(f"⚠️ MP impossible pour {member.name}")
                
                # Marquer comme notifié
                result.notified = True
                db.commit()
                
            except Exception as e:
                print(f"❌ Erreur pour {result.user_id}: {e}")
        
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"❌ Erreur check_results_task: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


@check_results_task.before_loop
async def before_check_results():
    """Attend que le bot soit prêt avant de démarrer la tâche"""
    await bot.wait_until_ready()


@bot.event
async def on_member_join(member: discord.Member):
    """
    ONBOARDING AUTOMATIQUE
    Quand quelqu'un rejoint le serveur
    """
    guild = member.guild
    
    print(f"\n{'='*50}")
    print(f"👋 NOUVEAU MEMBRE : {member.name} (ID: {member.id})")
    
    try:
        # 1. Trouver le groupe disponible au niveau 1
        groupe = await get_available_group(guild, niveau=1)
        print(f"📌 Groupe attribué : {groupe}")
        
        # 2. Créer ou récupérer le rôle
        role = discord.utils.get(guild.roles, name=f"Groupe {groupe}")
        if not role:
            role = await guild.create_role(
                name=f"Groupe {groupe}",
                color=discord.Color.green(),
                mentionable=True
            )
            print(f"✅ Rôle créé : {role.name}")
        
        # 3. Attribuer le rôle
        await member.add_roles(role)
        print(f"✅ Rôle attribué")
        
        # 4. Créer les salons si nécessaire
        await create_group_channels(guild, groupe, role)
        print(f"✅ Salons créés/vérifiés")
        
        # 5. Enregistrer en base de données
        from db_connection import SessionLocal
        from models import Utilisateur, Cohorte
        
        db = SessionLocal()
        try:
            # Vérifier si existe déjà
            existing = db.query(Utilisateur).filter(Utilisateur.user_id == member.id).first()
            
            if not existing:
                # Créer ou récupérer la cohorte
                now = datetime.now()
                month = now.strftime("%b").upper()
                year = str(now.year)[-2:]
                cohorte_id = f"{month}{year}-A"
                
                cohorte = db.query(Cohorte).filter(Cohorte.id == cohorte_id).first()
                if not cohorte:
                    cohorte = Cohorte(
                        id=cohorte_id,
                        date_creation=now,
                        date_premier_examen=now + timedelta(days=14),
                        niveau_actuel=1,
                        statut='active'
                    )
                    db.add(cohorte)
                    db.flush()
                
                # Créer l'utilisateur
                new_user = Utilisateur(
                    user_id=member.id,
                    username=member.name,
                    cohorte_id=cohorte_id,
                    niveau_actuel=1,
                    groupe=groupe,
                    examens_reussis=0,
                    date_inscription=now
                )
                
                db.add(new_user)
                db.commit()
                print(f"✅ Utilisateur enregistré en DB")
        
        finally:
            db.close()
        
        # 6. Message de bienvenue
        try:
            embed = discord.Embed(
                title="🎓 Bienvenue dans la Formation Python !",
                description=f"Salut {member.mention}, nous sommes ravis de t'accueillir !",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📌 Ton Groupe",
                value=f"**Groupe {groupe}**\nTu as été assigné automatiquement.",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Prochaines Étapes",
                value=(
                    "1️⃣ Consulte les ressources dans ton salon\n"
                    "2️⃣ Prépare-toi pour l'examen du Niveau 1\n"
                    "3️⃣ Utilise `/my_info` pour voir tes infos\n"
                    f"4️⃣ Passe ton examen sur le site avec ton ID : `{member.id}`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🌐 Lien du Site",
                value="https://site-fromation.onrender.com/exams",
                inline=False
            )
            
            embed.add_field(
                name="🤖 Notification Automatique",
                value="Tu recevras automatiquement tes résultats en MP dès que tu auras terminé un examen !",
                inline=False
            )
            
            embed.set_footer(text=f"Ton ID Discord : {member.id}")
            
            await member.send(embed=embed)
            print(f"✅ Message de bienvenue envoyé")
        
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name}")
        
        print(f"🎉 Onboarding terminé pour {member.name}")
        print(f"{'='*50}\n")
    
    except Exception as e:
        print(f"❌ Erreur onboarding: {e}")
        import traceback
        traceback.print_exc()


async def get_available_group(guild: discord.Guild, niveau: int) -> str:
    """
    Trouve le premier groupe non plein pour un niveau donné
    Limite : 15 membres par groupe
    """
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    
    for letter in letters:
        groupe_name = f"{niveau}-{letter}"
        role = discord.utils.get(guild.roles, name=f"Groupe {groupe_name}")
        
        if role is None:
            return groupe_name
        
        member_count = len(role.members)
        
        if member_count < 15:
            return groupe_name
    
    return f"{niveau}-A"


async def create_group_channels(guild: discord.Guild, groupe: str, role: discord.Role):
    """
    Crée une catégorie et des salons pour un groupe
    """
    category_name = f"📚 Groupe {groupe}"
    
    # Vérifier si la catégorie existe déjà
    category = discord.utils.get(guild.categories, name=category_name)
    
    if category:
        return
    
    # Créer la catégorie
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    category = await guild.create_category(category_name, overwrites=overwrites)
    
    # Créer les salons
    await guild.create_text_channel(f"💬-discussion", category=category, overwrites=overwrites)
    await guild.create_text_channel(f"📖-ressources", category=category, overwrites=overwrites)
    await guild.create_text_channel(f"❓-entraide", category=category, overwrites=overwrites)
    
    print(f"✅ Catégorie et salons créés pour {groupe}")


@bot.tree.command(name="register", description="S'inscrire dans le système")
async def register(interaction: discord.Interaction):
    """Inscription manuelle"""
    await interaction.response.send_message("🔄 Inscription en cours...", ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    
    try:
        user_id = interaction.user.id
        username = interaction.user.name
        
        # Vérifier si existe déjà
        existing = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if existing:
            await interaction.edit_original_response(
                content=f"✅ **Déjà inscrit !**\n\n"
                       f"**Groupe** : {existing.groupe}\n"
                       f"**Niveau** : {existing.niveau_actuel}\n"
                       f"**ID** : `{user_id}`\n\n"
                       f"🌐 Site : https://site-fromation.onrender.com/exams"
            )
            return
        
        # Simuler l'onboarding
        member = interaction.guild.get_member(user_id)
        if member:
            await on_member_join(member)
            await asyncio.sleep(1)
            
            user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
            
            if user:
                await interaction.edit_original_response(
                    content=f"✅ **Inscription réussie !**\n\n"
                           f"**Groupe** : {user.groupe}\n"
                           f"**Niveau** : {user.niveau_actuel}\n"
                           f"**ID** : `{user_id}`\n\n"
                           f"🌐 Site : https://site-fromation.onrender.com/exams\n\n"
                           f"🤖 Tu recevras tes résultats automatiquement en MP !"
                )
        
    finally:
        db.close()


@bot.tree.command(name="check_exam_results", description="[ADMIN] Vérifier manuellement les résultats")
@commands.has_permissions(administrator=True)
async def check_exam_results(interaction: discord.Interaction):
    """
    Commande manuelle pour forcer la vérification
    (normalement, c'est automatique toutes les 30s)
    """
    await interaction.response.send_message("🔄 Vérification manuelle en cours...", ephemeral=True)
    
    # Forcer l'exécution de la tâche
    await check_results_task()
    
    await interaction.edit_original_response(
        content="✅ Vérification manuelle terminée !\n\n"
               "💡 Les résultats sont normalement traités automatiquement toutes les 30 secondes."
    )


@bot.tree.command(name="clear_db", description="[ADMIN] Vider la base de données")
@commands.has_permissions(administrator=True)
async def clear_db(interaction: discord.Interaction):
    """Vide toute la base de données"""
    await interaction.response.send_message(
        "⚠️ **ATTENTION** ⚠️\n\nSupprimer TOUTES les données ?\nClique pour confirmer.",
        view=ConfirmClearView(),
        ephemeral=True
    )


class ConfirmClearView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
    
    @discord.ui.button(label="✅ OUI, VIDER", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        from db_connection import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        
        try:
            db.execute(text("DELETE FROM exam_results"))
            db.execute(text("DELETE FROM utilisateurs"))
            db.execute(text("DELETE FROM cohortes"))
            db.commit()
            
            await interaction.edit_original_response(
                content="✅ Base de données vidée !",
                view=None
            )
        
        finally:
            db.close()
    
    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ Annulé",
            view=None
        )


@bot.tree.command(name="my_info", description="Voir mes informations")
async def my_info(interaction: discord.Interaction):
    """Affiche les infos de l'utilisateur"""
    await interaction.response.defer(ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    
    try:
        user = db.query(Utilisateur).filter(Utilisateur.user_id == interaction.user.id).first()
        
        if not user:
            await interaction.followup.send("❌ Pas inscrit. Utilise `/register`", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 Tes Informations", color=discord.Color.blue())
        embed.add_field(name="👥 Groupe", value=f"**{user.groupe}**", inline=True)
        embed.add_field(name="📊 Niveau", value=f"**{user.niveau_actuel}**", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{user.user_id}`", inline=True)
        embed.add_field(
            name="🌐 Lien Examen",
            value=f"https://site-fromation.onrender.com/exams\nID : `{user.user_id}`",
            inline=False
        )
        embed.add_field(
            name="🤖 Automatique",
            value="Tu recevras tes résultats automatiquement en MP après chaque examen !",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()


@bot.tree.command(name="list_users", description="[ADMIN] Liste tous les utilisateurs")
@commands.has_permissions(administrator=True)
async def list_users(interaction: discord.Interaction):
    """Liste tous les utilisateurs"""
    await interaction.response.defer(ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    
    try:
        users = db.query(Utilisateur).all()
        
        if not users:
            await interaction.followup.send("📭 Aucun utilisateur", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"👥 Utilisateurs ({len(users)})", color=discord.Color.blue())
        
        for user in users[:25]:
            embed.add_field(
                name=f"{user.username}",
                value=f"ID: `{user.user_id}`\nGroupe: {user.groupe}\nNiveau: {user.niveau_actuel}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()


@bot.tree.command(name="task_status", description="[ADMIN] Statut de la tâche automatique")
@commands.has_permissions(administrator=True)
async def task_status(interaction: discord.Interaction):
    """Affiche le statut de la tâche automatique"""
    await interaction.response.defer(ephemeral=True)
    
    status = "✅ Active" if check_results_task.is_running() else "❌ Inactive"
    
    embed = discord.Embed(
        title="🤖 Statut de la Tâche Automatique",
        color=discord.Color.green() if check_results_task.is_running() else discord.Color.red()
    )
    
    embed.add_field(name="Statut", value=status, inline=True)
    embed.add_field(name="Intervalle", value="30 secondes", inline=True)
    embed.add_field(
        name="Fonction",
        value="Vérifie automatiquement les nouveaux résultats d'examens et notifie les utilisateurs",
        inline=False
    )
    
    await interaction.followup.send(embed=embed, ephemeral=True)


def get_courses_for_level(niveau: int) -> list:
    """
    Retourne la liste des IDs de cours pour un niveau donné
    """
    courses_map = {
        1: [1],  # Niveau 1 : POO
        2: [2],  # Niveau 2 : Structures de données
        3: [3],  # Niveau 3 : Exceptions
        4: [4],  # Niveau 4 : Algorithmique
        5: []    # Niveau 5 : Pas de cours (niveau final)
    }
    return courses_map.get(niveau, [])


async def setup_resources_channels():
    """
    Crée les salons #ressources-niveau-X et envoie les cours automatiquement
    """
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    try:
        # Récupérer tous les niveaux actifs
        niveaux_actifs = db.query(Utilisateur.niveau_actuel).distinct().all()
        niveaux_actifs = [n[0] for n in niveaux_actifs]
        
        print(f"📚 Niveaux actifs détectés : {niveaux_actifs}")
        
        for guild in bot.guilds:
            for niveau in niveaux_actifs:
                channel_name = f"ressources-niveau-{niveau}"
                
                # Vérifier si le salon existe déjà
                existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
                
                if not existing_channel:
                    # Créer le salon
                    print(f"🔨 Création du salon {channel_name}...")
                    
                    # Trouver la catégorie "Niveau X" si elle existe
                    category = discord.utils.get(guild.categories, name=f"Niveau {niveau}")
                    
                    existing_channel = await guild.create_text_channel(
                        channel_name,
                        category=category,
                        topic=f"📚 Ressources et cours pour le niveau {niveau}"
                    )
                    print(f"✅ Salon {channel_name} créé")
                
                # Envoyer les cours pour ce niveau
                course_ids = get_courses_for_level(niveau)
                
                if not course_ids:
                    print(f"ℹ️ Pas de cours pour le niveau {niveau}")
                    continue
                
                print(f"📤 Envoi de {len(course_ids)} cours dans {channel_name}...")
                
                for course_id in course_ids:
                    await send_course_to_channel(course_id, existing_channel)
                    await asyncio.sleep(1)  # Pause entre chaque message
                
                print(f"✅ Cours envoyés dans {channel_name}")
    
    finally:
        db.close()


async def send_course_to_channel(course_id: int, channel: discord.TextChannel):
    """
    Envoie un cours avec son bouton quiz dans un salon
    """
    try:
        # Charger les infos du quiz
        quiz_path = f'quizzes/quiz_{course_id}.json'
        with open(quiz_path, 'r', encoding='utf-8') as f:
            quiz_data = json.load(f)
            course_title = quiz_data['course_title']
        
        # Créer l'embed
        embed = discord.Embed(
            title=f"📚 {course_title}",
            description=f"Accède au cours en ligne et teste tes connaissances !",
            color=discord.Color.blue()
        )
        
        # URL vers la page du cours
        course_url = f"https://site-fromation.onrender.com/course/{course_id}"
        
        embed.add_field(
            name="🌐 Lien du cours",
            value=f"[Cliquez ici pour accéder au cours]({course_url})",
            inline=False
        )
        
        embed.add_field(
            name="📝 Quiz Interactif",
            value="Clique sur le bouton ci-dessous pour faire le quiz en MP !",
            inline=False
        )
        
        # Créer la vue avec le bouton
        view = QuizButton(course_id)
        
        # Envoyer dans le salon
        await channel.send(embed=embed, view=view)
        print(f"  ✅ Cours {course_id} envoyé")
    
    except FileNotFoundError:
        print(f"  ❌ Quiz {course_id} introuvable")
    except Exception as e:
        print(f"  ❌ Erreur lors de l'envoi du cours {course_id}: {e}")


@bot.event
async def on_ready():
    """Appelé quand le bot est prêt"""
    print(f'✅ {bot.user} connecté')
    print(f'🔗 Connecté à {len(bot.guilds)} serveur(s)')
    
    # Synchroniser les commandes
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commande(s) synchronisée(s)')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')
    
    # Configurer les salons de ressources et envoyer les cours
    print("🔧 Configuration des salons de ressources...")
    await setup_resources_channels()
    print("✅ Configuration terminée")


class QuizButton(discord.ui.View):
    """Vue avec bouton pour démarrer le quiz"""
    
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
            
            # Vérifier l'utilisateur en DB
            from db_connection import SessionLocal
            from models import Utilisateur, Review
            from datetime import datetime, timedelta
            
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
                
                # Filtrer les questions selon SM-2
                now = datetime.now()
                questions_to_review = []
                
                for question in quiz_data['questions']:
                    q_id = question['id']
                    
                    # Vérifier si une review existe
                    review = db.query(Review).filter(
                        Review.user_id == interaction.user.id,
                        Review.question_id == q_id
                    ).first()
                    
                    if not review:
                        # Nouvelle question
                        questions_to_review.append(question)
                    elif review.next_review <= now:
                        # Question à réviser
                        questions_to_review.append(question)
                
                if not questions_to_review:
                    await interaction.followup.send(
                        "✅ Tu as déjà révisé toutes les questions récemment !\n"
                        "Reviens plus tard pour continuer.",
                        ephemeral=True
                    )
                    return
                
                # Envoyer le quiz en MP
                embed = discord.Embed(
                    title=f"📝 Quiz : {quiz_data['course_title']}",
                    description=f"Tu as **{len(questions_to_review)} question(s)** à réviser.",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Instructions",
                    value=(
                        "Je vais te poser les questions une par une.\n"
                        "Réponds avec **A**, **B**, **C** ou **D**.\n\n"
                        "Ton score déterminera quand tu reverras cette question (SM-2)."
                    ),
                    inline=False
                )
                
                await interaction.user.send(embed=embed)
                
                # Démarrer le quiz
                await start_quiz_sm2(interaction.user, self.course_id, questions_to_review, db)
                
                await interaction.followup.send(
                    f"✅ Quiz envoyé en MP ! Vérifie tes messages privés.",
                    ephemeral=True
                )
            
            finally:
                db.close()
        
        except FileNotFoundError:
            await interaction.followup.send(
                f"❌ Quiz introuvable pour le cours {self.course_id}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je ne peux pas t'envoyer de MP. Active tes messages privés !",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ Erreur quiz: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Erreur : {e}",
                ephemeral=True
            )


async def start_quiz_sm2(member: discord.Member, course_id: int, questions: list, db):
    """
    Démarre un quiz interactif en MP avec SM-2
    """
    from models import Review, CourseQuizResult
    from datetime import datetime, timedelta
    
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
        
        embed.add_field(
            name="Options",
            value=options_text,
            inline=False
        )
        
        await member.send(embed=embed)
        
        # Attendre la réponse
        def check(m):
            return (
                m.author.id == member.id and 
                isinstance(m.channel, discord.DMChannel) and 
                m.content.upper() in ['A', 'B', 'C', 'D']
            )
        
        try:
            msg = await bot.wait_for('message', check=check, timeout=300)  # 5 minutes
            user_answer = msg.content.upper()
            correct_answer = question['correct']
            
            # Vérifier la réponse
            if user_answer == correct_answer:
                quality = 5  # Parfait
                result_embed = discord.Embed(
                    title="✅ Correct !",
                    description=question.get('explanation', ''),
                    color=discord.Color.green()
                )
            else:
                quality = 0  # Échec
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
            
            # Appliquer l'algorithme SM-2
            review = db.query(Review).filter(
                Review.user_id == member.id,
                Review.question_id == question['id']
            ).first()
            
            if not review:
                # Nouvelle question
                review = Review(
                    user_id=member.id,
                    question_id=question['id'],
                    next_review=datetime.now(),
                    interval_days=1.0,
                    repetitions=0,
                    easiness_factor=2.5
                )
                db.add(review)
            
            # Algorithme SM-2
            if quality >= 3:
                # Bonne réponse
                if review.repetitions == 0:
                    review.interval_days = 1
                elif review.repetitions == 1:
                    review.interval_days = 6
                else:
                    review.interval_days = review.interval_days * review.easiness_factor
                
                review.repetitions += 1
            else:
                # Mauvaise réponse
                review.repetitions = 0
                review.interval_days = 1
            
            # Ajuster easiness_factor
            review.easiness_factor = max(
                1.3,
                review.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            )
            
            # Prochaine révision
            review.next_review = datetime.now() + timedelta(days=review.interval_days)
            
            # Sauvegarder le résultat
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
            await member.send("⏱️ Temps écoulé ! Quiz annulé.")
            return
    
    # Fin du quiz
    await member.send(
        f"🎉 **Quiz terminé !**\n\n"
        f"Tu as répondu à **{total_questions} question(s)**.\n"
        f"Continue à réviser pour maîtriser le sujet ! 💪"
    )


async def on_user_level_change(user_id: int, new_level: int, guild: discord.Guild):
    """
    Appelé quand un utilisateur change de niveau
    Envoie les cours du nouveau niveau dans le salon ressources
    """
    channel_name = f"ressources-niveau-{new_level}"
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    
    if not channel:
        # Créer le salon s'il n'existe pas
        category = discord.utils.get(guild.categories, name=f"Niveau {new_level}")
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            topic=f"📚 Ressources et cours pour le niveau {new_level}"
        )
    
    # Vérifier si les cours ont déjà été envoyés
    # (pour éviter les doublons)
    async for message in channel.history(limit=50):
        if message.author == bot.user and message.embeds:
            # Les cours sont déjà là
            return
    
    # Envoyer les cours
    course_ids = get_courses_for_level(new_level)
    for course_id in course_ids:
        await send_course_to_channel(course_id, channel)
        await asyncio.sleep(1)


@bot.tree.command(name="setup_resources", description="[ADMIN] Configurer les salons de ressources")
@commands.has_permissions(administrator=True)
async def setup_resources_command(interaction: discord.Interaction):
    """
    Force la création des salons de ressources et l'envoi des cours
    """
    await interaction.response.defer(ephemeral=True)
    
    try:
        await setup_resources_channels()
        await interaction.followup.send(
            "✅ Salons de ressources configurés avec succès !",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Erreur : {e}",
            ephemeral=True
        )


if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    print("🤖 Tâche automatique : Activée (30s)")
    bot.run(token)
