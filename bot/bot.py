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
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import json
from vote_system import VoteSystem
from bonus_system import BonusSystem, check_finished_exam_periods
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

    # Ajouter colonne 'vote_start_time' dans exam_periods si nécessaire
    db = SessionLocal()
    try:
        check = text("SELECT column_name FROM information_schema.columns WHERE table_name='exam_periods' AND column_name='vote_start_time'")
        if not db.execute(check).fetchone():
            print("📝 Ajout colonne vote_start_time...")
            # Ajouter la colonne (nullable temporairement)
            db.execute(text("ALTER TABLE exam_periods ADD COLUMN vote_start_time TIMESTAMP NULL"))
            db.commit()

            # Calculer vote_start_time pour les périodes existantes (start_time - 24h)
            db.execute(text("""
                UPDATE exam_periods
                SET vote_start_time = start_time - INTERVAL '1 day'
                WHERE vote_start_time IS NULL
            """))
            db.commit()

            # Rendre la colonne NOT NULL
            db.execute(text("ALTER TABLE exam_periods ALTER COLUMN vote_start_time SET NOT NULL"))
            db.commit()
            print("✅ Colonne 'vote_start_time' ajoutée")
    except Exception as e:
        print(f"⚠️ Migration vote_start_time: {e}")
        db.rollback()
    finally:
        db.close()

    print("✅ Base de données prête")

except Exception as e:
    print(f"⚠️ Erreur DB: {e}")

print("=" * 50)

# Configuration du bot


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
        
    if not check_finished_exam_periods.is_running():
        check_finished_exam_periods.start()
        print("✅ Système de bonus automatique démarré")

# ... vos imports existants ...
from discord.ext import tasks # Assurez-vous d'avoir cet import
from bonus_system import BonusSystem # Importez juste la classe

# ... (le début de votre fichier bot.py reste pareil) ...

# ✅ AJOUTEZ CETTE TÂCHE DANS BOT.PY (pas dans bonus_system.py)
@tasks.loop(minutes=5)
async def check_finished_exam_periods():
    """
    Vérifie toutes les 5 minutes s'il y a des périodes d'examen terminées
    et applique les bonus automatiquement
    """
    from db_connection import SessionLocal
    from models import ExamPeriod
    
    db = SessionLocal()
    try:
        now = datetime.now()
        
        # Trouver les périodes terminées mais non traitées
        finished_periods = db.query(ExamPeriod).filter(
            ExamPeriod.end_time <= now,
            ExamPeriod.bonuses_applied == False
        ).all()
        
        if not finished_periods:
            return
        
        print(f"\n🔔 {len(finished_periods)} période(s) d'examen terminée(s) détectée(s)")
        
        # On instancie le système avec le bot disponible ici
        bonus_system = BonusSystem(bot)
        
        for period in finished_periods:
            # Récupérer le guild (serveur Discord)
            guild = bot.guilds[0] if bot.guilds else None
            
            if not guild:
                print(f"❌ Aucun serveur Discord disponible")
                continue
            
            await bonus_system.apply_bonuses_for_period(period, guild)
    
    except Exception as e:
        print(f"❌ Erreur check_finished_exam_periods: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

# ✅ ATTENDRE QUE LE BOT SOIT PRÊT AVANT DE LANCER
@check_finished_exam_periods.before_loop
async def before_check_finished_exam_periods():
    await bot.wait_until_ready()
    print("⏰ Vérification des périodes d'examen démarrée (toutes les 5 min)")

# ... (reste du code) ...

@bot.event
async def on_ready():
    global discord_group_manager
    
    print(f'✅ Bot connecté en tant que {bot.user}')
    
    # ... (vos autres initialisations) ...
    
    # ✅ DÉMARRAGE DE LA TÂCHE ICI
    if not check_finished_exam_periods.is_running():
        check_finished_exam_periods.start()
        print("✅ Système de bonus automatique démarré")

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
                    await on_user_level_change(user_db.user_id, user_db.niveau_actuel, new_groupe, main_guild)
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


# ==================== SYSTÈME DE QUIZ ====================

# Charger les quiz
with open('quizzes.json', 'r', encoding='utf-8') as f:
    QUIZZES_DATA = json.load(f)


# ==================== SYSTÈME DE QUIZ (AVEC JSON UNIQUEMENT) ====================

class QuizButton(discord.ui.View):
    """Bouton pour démarrer le quiz - VERSION SIMPLIFIÉE AVEC JSON"""

    def __init__(self, course_id: int):
        super().__init__(timeout=None)
        self.course_id = course_id

    @discord.ui.button(label="📝 Faire le Quiz", style=discord.ButtonStyle.primary, custom_id="quiz_button")
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Démarre le quiz en MP"""
        await interaction.response.defer(ephemeral=True)

        # Trouver le cours
        course = next((c for c in QUIZZES_DATA['courses'] if c['id'] == self.course_id), None)
        if not course:
            await interaction.followup.send("❌ Cours introuvable", ephemeral=True)
            return

        # Vérifier inscription
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(Utilisateur.user_id == interaction.user.id).first()
            if not user:
                await interaction.followup.send("❌ Tu dois d'abord t'inscrire avec `/register`", ephemeral=True)
                return
        finally:
            db.close()

        # Filtrer avec SM-2 (JSON uniquement, pas de SQL!)
        from quiz_reviews_manager import get_questions_to_review
        questions_to_review = get_questions_to_review(interaction.user.id, course['questions'])

        if not questions_to_review:
            await interaction.followup.send(
                "✅ Tu as déjà révisé toutes les questions !\n"
                "Reviens plus tard pour continuer. 📚",
                ephemeral=True
            )
            return

        # Envoyer en MP sans intro
        try:
            # Démarrer le quiz directement
            await start_quiz_interactive(interaction.user, course['title'], questions_to_review)
            await interaction.followup.send("✅ Quiz envoyé en MP !", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ Active tes messages privés !", ephemeral=True)


async def start_quiz_interactive(member: discord.Member, course_title: str, questions: list):
    """
    Quiz interactif en MP avec questions une par une
    Utilise l'algorithme SM-2 pour planifier les révisions
    """
    from quiz_reviews_manager import update_review_sm2

    total_questions = len(questions)
    correct_count = 0

    for i, question in enumerate(questions):
        # Envoyer la question
        embed = discord.Embed(
            title=f"Question {i+1}/{total_questions}",
            description=question['question'],
            color=discord.Color.blue()
        )

        # Les options sont une liste, pas un dict
        options_text = ""
        for idx, option in enumerate(question['options']):
            letter = chr(65 + idx)  # A, B, C, D
            options_text += f"**{letter}.** {option}\n"

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

            # Convertir la lettre en index (A=0, B=1, C=2, D=3)
            answer_index = ord(user_answer) - 65
            correct_index = question['correct']

            # Vérifier la réponse
            if answer_index == correct_index:
                quality = 5  # Parfait
                correct_count += 1
                result_embed = discord.Embed(
                    title="✅ Correct !",
                    description=question.get('explanation', ''),
                    color=discord.Color.green()
                )
            else:
                quality = 0  # Échec
                correct_letter = chr(65 + correct_index)
                result_embed = discord.Embed(
                    title="❌ Incorrect",
                    description=(
                        f"La bonne réponse était : **{correct_letter}. {question['options'][correct_index]}**\n\n"
                        f"{question.get('explanation', '')}"
                    ),
                    color=discord.Color.red()
                )

            await member.send(embed=result_embed)

            # Mettre à jour SM-2 et planifier le rappel automatique
            from quiz_reviews_manager import update_review_sm2
            from review_scheduler import schedule_review

            review_data = update_review_sm2(member.id, question['id'], quality)
            next_review_date = review_data['next_review_date']

            # Planifier le rappel automatique par MP
            schedule_review(bot, member.id, question, next_review_date)

            await asyncio.sleep(2)

        except asyncio.TimeoutError:
            await member.send("⏱️ Temps écoulé ! Quiz annulé.")
            return

    # Fin du quiz
    score_pct = (correct_count / total_questions) * 100
    await member.send(
        f"🎉 **Quiz terminé !**\n\n"
        f"📊 Score : **{correct_count}/{total_questions}** ({score_pct:.0f}%)\n"
        f"Continue à réviser pour maîtriser le sujet ! 💪"
    )


# ==================== VUE POUR RÉVISIONS AUTOMATIQUES ====================

class ReviewQuestionView(discord.ui.View):
    """Vue avec boutons A/B/C/D pour répondre aux questions de révision"""

    def __init__(self, question_data: dict, user_id: int):
        super().__init__(timeout=None)  # Pas de timeout !
        self.question_data = question_data
        self.user_id = user_id
        self.answered = False

        # Créer les boutons A, B, C, D
        num_options = len(question_data['options'])
        for i in range(num_options):
            letter = chr(65 + i)  # A, B, C, D
            button = discord.ui.Button(
                label=letter,
                style=discord.ButtonStyle.primary,
                custom_id=f"review_answer_{letter}"
            )
            button.callback = self.create_callback(i, letter)
            self.add_item(button)

    def create_callback(self, answer_index: int, letter: str):
        async def callback(interaction: discord.Interaction):
            # Vérifier que c'est bien l'utilisateur concerné
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "❌ Cette question n'est pas pour toi !",
                    ephemeral=True
                )
                return

            # Empêcher les réponses multiples
            if self.answered:
                await interaction.response.send_message(
                    "❌ Tu as déjà répondu à cette question !",
                    ephemeral=True
                )
                return

            self.answered = True
            await interaction.response.defer()

            # Vérifier la réponse
            correct_index = self.question_data['correct']
            is_correct = (answer_index == correct_index)

            # Qualité pour SM-2
            quality = 5 if is_correct else 0

            # Désactiver tous les boutons et colorer
            for item in self.children:
                item.disabled = True
                if isinstance(item, discord.ui.Button):
                    # Bouton correct en vert
                    if item.label == chr(65 + correct_index):
                        item.style = discord.ButtonStyle.success
                    # Mauvaise réponse en rouge
                    elif item.label == letter and not is_correct:
                        item.style = discord.ButtonStyle.danger

            # Mettre à jour le message avec les boutons colorés
            await interaction.message.edit(view=self)

            # Créer l'embed de résultat
            if is_correct:
                result_embed = discord.Embed(
                    title="✅ Correct !",
                    description=self.question_data.get('explanation', 'Bonne réponse !'),
                    color=discord.Color.green()
                )
            else:
                correct_letter = chr(65 + correct_index)
                result_embed = discord.Embed(
                    title="❌ Incorrect",
                    description=(
                        f"La bonne réponse était : **{correct_letter}. {self.question_data['options'][correct_index]}**\n\n"
                        f"{self.question_data.get('explanation', '')}"
                    ),
                    color=discord.Color.red()
                )

            # Mettre à jour SM-2 et planifier la prochaine révision
            from quiz_reviews_manager import update_review_sm2
            from review_scheduler import schedule_review, complete_question

            review_data = update_review_sm2(self.user_id, self.question_data['id'], quality)
            next_review_date = review_data['next_review_date']

            # Planifier la prochaine révision
            schedule_review(bot, self.user_id, self.question_data, next_review_date)

            # Ajouter info sur la prochaine révision
            if review_data['interval_days'] < 1:
                interval_text = f"{int(review_data['interval_days'] * 24)}h"
            elif review_data['interval_days'] == 1:
                interval_text = "1 jour"
            else:
                interval_text = f"{int(review_data['interval_days'])} jours"

            result_embed.add_field(
                name="📅 Prochaine révision",
                value=f"Dans {interval_text} ({next_review_date.strftime('%d/%m/%Y à %H:%M')})",
                inline=False
            )

            await interaction.followup.send(embed=result_embed)

            # Marquer la question comme répondue et envoyer la suivante si elle existe
            next_question = complete_question(self.user_id)
            if next_question:
                await asyncio.sleep(2)
                # Envoyer la question suivante
                embed = discord.Embed(
                    title="🔔 Question suivante",
                    description=next_question['question'],
                    color=discord.Color.blue()
                )

                options_text = ""
                for idx, option in enumerate(next_question['options']):
                    opt_letter = chr(65 + idx)
                    options_text += f"**{opt_letter}.** {option}\n"

                embed.add_field(name="Options", value=options_text, inline=False)
                embed.set_footer(text="Réponds quand tu es prêt !")

                view = ReviewQuestionView(next_question, self.user_id)
                await interaction.user.send(embed=embed, view=view)

        return callback


# ==================== COMMANDES ADMIN ====================

@bot.tree.command(name="send_course", description="[ADMIN] Envoyer un cours avec quiz")
@commands.has_permissions(administrator=True)
async def send_course(interaction: discord.Interaction, course_id: int, channel: discord.TextChannel = None):
    """
    Envoie un cours avec bouton quiz

    Args:
        course_id: ID du cours (1, 2, 3, 4)
        channel: Salon où envoyer (optionnel, défaut = salon actuel)
    """
    await interaction.response.defer(ephemeral=True)

    if channel is None:
        channel = interaction.channel

    # Vérifier que le cours existe
    course = next((c for c in QUIZZES_DATA['courses'] if c['id'] == course_id), None)

    if not course:
        await interaction.followup.send(
            f"❌ Cours {course_id} introuvable. IDs disponibles : 1, 2, 3, 4",
            ephemeral=True
        )
        return

    # Utiliser la fonction helper pour envoyer le cours
    await send_course_to_channel(course_id, channel)

    await interaction.followup.send(
        f"✅ Cours **{course['title']}** envoyé dans {channel.mention}",
        ephemeral=True
    )


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
    Envoie les cours dans les salons 📖-ressources de chaque groupe existant
    """
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    try:
        # Récupérer tous les groupes actifs
        groupes_actifs = db.query(Utilisateur.groupe, Utilisateur.niveau_actuel).distinct().all()
        
        print(f"📚 Groupes actifs détectés : {len(groupes_actifs)}")
        
        for guild in bot.guilds:
            for groupe, niveau in groupes_actifs:
                # Trouver la catégorie "📚 Groupe X-Y" (avec emoji livre + espace)
                category_name = f"📚 Groupe {groupe}"
                category = discord.utils.get(guild.categories, name=category_name)
                
                if not category:
                    print(f"⚠️ Catégorie '{category_name}' introuvable")
                    continue
                
                # Chercher le salon 📖-ressources (livre ouvert) dans cette catégorie
                resources_channel = None
                for channel in category.text_channels:
                    if channel.name == "📖-ressources":
                        resources_channel = channel
                        break
                
                if not resources_channel:
                    print(f"⚠️ Salon 📖-ressources introuvable dans {category_name}")
                    continue
                
                # Vérifier si les cours ont déjà été envoyés
                messages_count = 0
                async for message in resources_channel.history(limit=50):
                    if message.author == bot.user and message.embeds:
                        messages_count += 1
                
                course_ids = get_courses_for_level(niveau)
                
                if messages_count >= len(course_ids) and messages_count > 0:
                    print(f"✅ Cours déjà envoyés dans {category_name}")
                    continue
                
                if not course_ids:
                    print(f"ℹ️ Pas de cours pour le niveau {niveau}")
                    continue
                
                print(f"📤 Envoi de {len(course_ids)} cours dans {category_name} 📖-ressources...")
                
                for course_id in course_ids:
                    await send_course_to_channel(course_id, resources_channel)
                    await asyncio.sleep(1)
                
                print(f"✅ Cours envoyés dans {category_name}")
    
    finally:
        db.close()


async def send_course_to_channel(course_id: int, channel: discord.TextChannel):
    """
    Envoie un cours avec son bouton quiz dans un salon
    Utilise QUIZZES_DATA (déjà chargé en mémoire)
    """
    try:
        # Trouver le cours dans les données déjà chargées
        course = next((c for c in QUIZZES_DATA['courses'] if c['id'] == course_id), None)

        if not course:
            print(f"  ❌ Cours {course_id} introuvable")
            return
        
        course_title = course['title']
        
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

    # Démarrer le planificateur de révisions
    print("📅 Démarrage du planificateur de révisions...")
    from review_scheduler import start_scheduler, load_scheduled_reviews
    start_scheduler()
    load_scheduled_reviews(bot, QUIZZES_DATA)
    print("✅ Planificateur de révisions prêt")


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
# ==================== COMMANDE /vote ====================
@bot.tree.command(name="vote", description="Voter pour 1 à 3 personnes qui t'ont aidé")
@app_commands.describe(
    user1="Première personne à récompenser",
    user2="Deuxième personne à récompenser (optionnel)",
    user3="Troisième personne à récompenser (optionnel)"
)
async def vote(
    interaction: discord.Interaction,
    user1: discord.Member,
    user2: discord.Member = None,
    user3: discord.Member = None
):
    """Commande pour voter"""
    vote_system = VoteSystem(bot)
    await vote_system.vote_command(interaction, user1, user2, user3)


# ==================== COMMANDE /create_exam_period ====================
@bot.tree.command(name="create_exam_period", description="[ADMIN] Créer une période d'examen de 6h")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    group="Numéro du groupe (1-5)",
    start_time="Date et heure de début (format: YYYY-MM-DD HH:MM)"
)
async def create_exam_period(
    interaction: discord.Interaction,
    group: int,
    start_time: str
):
    """Crée une période d'examen de 6h"""
    await interaction.response.defer(ephemeral=True)
    
    from datetime import datetime, timedelta
    from db_connection import SessionLocal
    from models import ExamPeriod
    
    try:
        # Parser la date
        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = start + timedelta(hours=6)
        vote_start = start - timedelta(days=1)  # Votes ouverts 24h avant

        # Générer l'ID
        period_id = f"{start.strftime('%Y-%m-%d')}_group{group}"

        # Créer la période
        db = SessionLocal()
        try:
            # Vérifier si une période existe déjà
            existing = db.query(ExamPeriod).filter(ExamPeriod.id == period_id).first()
            if existing:
                await interaction.followup.send(
                    f"⚠️ **Une période d'examen existe déjà !**\n\n"
                    f"🆔 ID: `{period_id}`\n"
                    f"📊 Groupe: Niveau {existing.group_number}\n"
                    f"⏰ Début: {existing.start_time.strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"💡 Pour créer une nouvelle période:\n"
                    f"• Utilise une date différente, OU\n"
                    f"• Supprime d'abord l'ancienne avec `/delete_exam_period {period_id}`",
                    ephemeral=True
                )
                return

            period = ExamPeriod(
                id=period_id,
                group_number=group,
                vote_start_time=vote_start,
                start_time=start,
                end_time=end,
                votes_closed=False,
                bonuses_applied=False
            )

            db.add(period)
            db.commit()

            embed = discord.Embed(
                title="✅ Période d'Examen Créée",
                color=discord.Color.green()
            )

            embed.add_field(name="🆔 ID", value=period_id, inline=False)
            embed.add_field(name="📊 Groupe", value=f"Niveau {group}", inline=True)
            embed.add_field(name="🗳️ Votes ouverts", value=vote_start.strftime("%d/%m/%Y %H:%M"), inline=False)
            embed.add_field(name="⏰ Début examen", value=start.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="🏁 Fin examen", value=end.strftime("%d/%m/%Y %H:%M"), inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

        finally:
            db.close()

    except ValueError:
        await interaction.followup.send(
            "❌ Format de date incorrect. Utilise : YYYY-MM-DD HH:MM",
            ephemeral=True
        )


@bot.tree.command(name="delete_exam_period", description="[ADMIN] Supprimer une période d'examen")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    period_id="ID de la période (format: YYYY-MM-DD_groupX)"
)
async def delete_exam_period(
    interaction: discord.Interaction,
    period_id: str
):
    """Supprime une période d'examen"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import ExamPeriod

    db = SessionLocal()
    try:
        period = db.query(ExamPeriod).filter(ExamPeriod.id == period_id).first()

        if not period:
            await interaction.followup.send(
                f"❌ Aucune période d'examen trouvée avec l'ID `{period_id}`",
                ephemeral=True
            )
            return

        # Afficher les infos avant suppression
        info_msg = (
            f"🗑️ **Période d'examen supprimée**\n\n"
            f"🆔 ID: `{period.id}`\n"
            f"📊 Groupe: Niveau {period.group_number}\n"
            f"🗳️ Votes: {period.vote_start_time.strftime('%d/%m/%Y %H:%M')}\n"
            f"⏰ Début: {period.start_time.strftime('%d/%m/%Y %H:%M')}\n"
            f"🏁 Fin: {period.end_time.strftime('%d/%m/%Y %H:%M')}"
        )

        db.delete(period)
        db.commit()

        await interaction.followup.send(info_msg, ephemeral=True)

    finally:
        db.close()


@bot.tree.command(name="list_exam_periods", description="[ADMIN] Lister toutes les périodes d'examen")
@commands.has_permissions(administrator=True)
async def list_exam_periods_command(interaction: discord.Interaction):
    """Liste toutes les périodes d'examen"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import ExamPeriod
    from datetime import datetime

    db = SessionLocal()
    try:
        periods = db.query(ExamPeriod).order_by(ExamPeriod.start_time).all()

        if not periods:
            await interaction.followup.send(
                "📋 Aucune période d'examen configurée",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Périodes d'Examen",
            color=discord.Color.blue()
        )

        now = datetime.now()

        for period in periods:
            status = "🟢 À venir" if period.start_time > now else "🔴 Passée"
            if period.bonuses_applied:
                status = "✅ Terminée"

            value = (
                f"**ID:** `{period.id}`\n"
                f"**Votes:** {period.vote_start_time.strftime('%d/%m/%Y %H:%M')}\n"
                f"**Début:** {period.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                f"**Fin:** {period.end_time.strftime('%d/%m/%Y %H:%M')}\n"
                f"**Statut:** {status}"
            )

            embed.add_field(
                name=f"Groupe {period.group_number}",
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    finally:
        db.close()


# ==================== COMMANDE /my_vote_status ====================
@bot.tree.command(name="my_vote_status", description="Vérifier si tu as voté")
async def my_vote_status(interaction: discord.Interaction):
    """Vérifie si l'utilisateur a voté"""
    await interaction.response.defer(ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur, Vote
    
    db = SessionLocal()
    try:
        user = db.query(Utilisateur).filter(
            Utilisateur.user_id == interaction.user.id
        ).first()
        
        if not user:
            await interaction.followup.send(
                "❌ Tu n'es pas inscrit. Utilise `/register`",
                ephemeral=True
            )
            return
        
        vote_system = VoteSystem(bot)
        exam_period = vote_system.get_active_exam_period(user.niveau_actuel)
        
        if not exam_period:
            await interaction.followup.send(
                "ℹ️ Aucune période d'examen active pour ton groupe.",
                ephemeral=True
            )
            return
        
        votes = db.query(Vote).filter(
            Vote.voter_id == interaction.user.id,
            Vote.exam_period_id == exam_period.id
        ).all()
        
        if len(votes) == 0:
            embed = discord.Embed(
                title="⚠️ Tu n'as pas encore voté",
                description=f"Tu dois voter avant de passer l'examen !",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📝 Comment voter ?",
                value="Utilise `/vote @user1 @user2 @user3`",
                inline=False
            )
        else:
            voted_for = [f"• <@{vote.voted_for_id}>" for vote in votes]
            embed = discord.Embed(
                title="✅ Tu as déjà voté",
                color=discord.Color.green()
            )
            embed.add_field(
                name=f"👥 Tes Votes ({len(votes)})",
                value="\n".join(voted_for),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    print("🤖 Tâche automatique : Activée (30s)")
    bot.run(token)
