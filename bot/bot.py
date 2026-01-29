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
from bonus_system import BonusSystem, start_bonus_scheduler, load_pending_exam_periods, schedule_bonus_application
# Keep-alive
from stay_alive import keep_alive, set_bot
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

    print(f'✅ {bot.user} connecté')
    print(f'🔗 Connecté à {len(bot.guilds)} serveur(s)')

    # Définir le serveur principal
    if bot.guilds:
        main_guild = bot.guilds[0]

    # Permettre à l'API Flask d'accéder au bot
    set_bot(bot)
    print("✅ API Flask initialisée avec le bot Discord")

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

    # Démarrer le planificateur de bonus (application automatique à la fin des périodes)
    print("🎁 Démarrage du planificateur de bonus...")
    start_bonus_scheduler()
    load_pending_exam_periods(bot)
    print("✅ Planificateur de bonus prêt")


# ANCIENNE MÉTHODE : Vérification périodique toutes les 30 secondes (DÉSACTIVÉE)
# La promotion se fait maintenant immédiatement via l'API /api/promote
# @tasks.loop(seconds=30)
# async def check_results_task():
#     pass


@bot.event
async def on_member_join(member: discord.Member):
    """
    ONBOARDING AUTOMATIQUE
    Quand quelqu'un rejoint le serveur, il obtient le rôle "nouveau"
    et a accès uniquement au canal d'inscription
    """
    guild = member.guild

    print(f"\n{'='*50}")
    print(f"👋 NOUVEAU MEMBRE : {member.name} (ID: {member.id})")

    try:
        # 1. Créer ou récupérer le rôle "nouveau"
        nouveau_role = discord.utils.get(guild.roles, name="nouveau")
        if not nouveau_role:
            nouveau_role = await guild.create_role(
                name="nouveau",
                color=discord.Color.light_grey(),
                mentionable=False,
                hoist=False
            )
            print(f"✅ Rôle 'nouveau' créé")

        # 2. Attribuer le rôle "nouveau"
        await member.add_roles(nouveau_role)
        print(f"✅ Rôle 'nouveau' attribué à {member.name}")

        # 3. Configurer les permissions du canal d'inscription (si nécessaire)
        inscription_channel = guild.get_channel(1462439274178674950)
        if inscription_channel:
            # Vérifier si les permissions sont correctement configurées
            overwrites = inscription_channel.overwrites

            # S'assurer que @everyone ne peut pas voir le canal
            if guild.default_role not in overwrites or overwrites[guild.default_role].read_messages != False:
                await inscription_channel.set_permissions(
                    guild.default_role,
                    read_messages=False
                )

            # S'assurer que le rôle "nouveau" peut voir le canal
            if nouveau_role not in overwrites or overwrites[nouveau_role].read_messages != True:
                await inscription_channel.set_permissions(
                    nouveau_role,
                    read_messages=True,
                    send_messages=True
                )

            print(f"✅ Permissions du canal d'inscription configurées")

        # 4. Message de bienvenue en MP
        try:
            embed = discord.Embed(
                title="🎓 Bienvenue dans la Formation Python !",
                description=f"Salut {member.mention}, nous sommes ravis de t'accueillir !",
                color=discord.Color.green()
            )

            if inscription_channel:
                embed.add_field(
                    name="📝 Inscription",
                    value=f"Pour t'inscrire, rends-toi dans le canal <#{inscription_channel.id}> et tape la commande `/register`",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 Inscription",
                    value="Pour t'inscrire, tape la commande `/register` dans n'importe quel canal où tu as accès.",
                    inline=False
                )

            embed.add_field(
                name="🎯 Prochaines Étapes",
                value=(
                    "1️⃣ Inscris-toi avec `/register`\n"
                    "2️⃣ Tu seras automatiquement assigné à un groupe\n"
                    "3️⃣ Accède aux ressources et prépare-toi pour l'examen\n"
                    "4️⃣ Passe ton examen quand tu es prêt"
                ),
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
    Format: groupe-1-a-entraide, groupe-1-a-ressources, etc.
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

    # Créer les salons avec le bon format de nommage
    groupe_lower = groupe.lower()
    await guild.create_text_channel(f"groupe-{groupe_lower}-ressources", category=category, overwrites=overwrites)
    await guild.create_text_channel(f"groupe-{groupe_lower}-entraide", category=category, overwrites=overwrites)
    await guild.create_voice_channel(f"🎙️ Vocal {groupe}", category=category, overwrites=overwrites)

    # Créer le salon "mon-examen" (lecture seule, seul le bot peut écrire)
    exam_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        role: discord.PermissionOverwrite(read_messages=True, send_messages=False),  # Lecture seule pour les membres
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Bot peut écrire
    }
    await guild.create_text_channel(f"📝-mon-examen", category=category, overwrites=exam_overwrites)

    print(f"✅ Catégorie et salons créés pour {groupe}")


@bot.tree.command(name="register", description="S'inscrire dans le système")
async def register(interaction: discord.Interaction):
    """Inscription manuelle"""
    await interaction.response.send_message("🔄 Inscription en cours...", ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur
    from group_manager import GroupManager

    db = SessionLocal()

    try:
        user_id = interaction.user.id
        username = interaction.user.name
        member = interaction.guild.get_member(user_id)

        if not member:
            await interaction.edit_original_response(
                content="❌ Erreur : impossible de récupérer tes informations."
            )
            return

        # Vérifier si existe déjà
        existing = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if existing:
            await interaction.edit_original_response(
                content=f"✅ **Déjà inscrit !**\n\n"
                       f"**Groupe** : {existing.groupe}\n"
                       f"**Niveau** : {existing.niveau_actuel}\n"
                       f"**ID** : `{user_id}`\n\n"
                       f"🌐 Site : http://localhost:5000/exams"
            )
            return

        # Utiliser le GroupManager pour l'inscription
        group_manager = GroupManager(db)
        groupe, info = group_manager.register_user(user_id, username, niveau=1)

        if info['status'] == 'direct':
            # Inscription réussie
            # Retirer le rôle "nouveau"
            nouveau_role = discord.utils.get(interaction.guild.roles, name="nouveau")
            if nouveau_role and nouveau_role in member.roles:
                await member.remove_roles(nouveau_role)
                print(f"✅ Rôle 'nouveau' retiré de {username}")

            # Créer ou récupérer le rôle du groupe
            role = discord.utils.get(interaction.guild.roles, name=f"Groupe {groupe}")
            if not role:
                role = await interaction.guild.create_role(
                    name=f"Groupe {groupe}",
                    color=discord.Color.green(),
                    mentionable=True,
                    hoist=True
                )
                print(f"✅ Rôle créé : {role.name}")

            # Attribuer le rôle du groupe
            await member.add_roles(role)
            print(f"✅ Rôle attribué : {role.name}")

            # Créer les salons si nécessaire
            await create_group_channels(interaction.guild, groupe, role)
            print(f"✅ Salons créés/vérifiés")

            await interaction.edit_original_response(
                content=f"✅ **Inscription réussie !**\n\n"
                       f"**Groupe** : {groupe}\n"
                       f"**Niveau** : 1\n"
                       f"**ID** : `{user_id}`\n\n"
                       f"🌐 Site : http://localhost:5000/exams\n\n"
                       f"🤖 Tu recevras tes résultats automatiquement en MP !"
            )

        elif info['status'] == 'waiting_list':
            # Ajouté à la waiting list
            await interaction.edit_original_response(
                content=f"⏳ **Ajouté à la liste d'attente**\n\n"
                       f"**Raison** : {info.get('raison', 'Groupes pleins')}\n\n"
                       f"Tu seras automatiquement assigné dès qu'une place se libère ou qu'un nouveau groupe est créé."
            )

    except Exception as e:
        print(f"❌ Erreur lors de l'inscription : {e}")
        import traceback
        traceback.print_exc()
        await interaction.edit_original_response(
            content=f"❌ Erreur lors de l'inscription : {e}"
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
            # Supprimer dans l'ordre à cause des contraintes de clés étrangères
            print("🗑️  Suppression des votes...")
            db.execute(text("DELETE FROM votes"))

            print("🗑️  Suppression des périodes d'examen...")
            db.execute(text("DELETE FROM exam_periods"))

            print("🗑️  Suppression des résultats d'examen...")
            db.execute(text("DELETE FROM exam_results"))

            print("🗑️  Suppression des utilisateurs...")
            db.execute(text("DELETE FROM utilisateurs"))

            print("🗑️  Suppression des cohortes...")
            db.execute(text("DELETE FROM cohortes"))

            db.commit()

            await interaction.edit_original_response(
                content="✅ Base de données complètement vidée !\n\n"
                        "🗑️ Votes supprimés\n"
                        "🗑️ Périodes d'examen supprimées\n"
                        "🗑️ Résultats d'examen supprimés\n"
                        "🗑️ Utilisateurs supprimés\n"
                        "🗑️ Cohortes supprimées",
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
            value=f"http://localhost:5000/exams\nID : `{user.user_id}`",
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
        course_url = f"http://localhost:5000/course/{course_id}"
        
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
@bot.tree.command(name="create_exam_period", description="[ADMIN] Créer une période d'examen de 30 minutes")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    group="Numéro du groupe (1-5)",
    start_time="Date et heure de début EN HEURE LOCALE (format: YYYY-MM-DD HH:MM)",
    timezone_offset="Décalage horaire par rapport à UTC (ex: +1 pour Paris, défaut: +1)"
)
async def create_exam_period(
    interaction: discord.Interaction,
    group: int,
    start_time: str,
    timezone_offset: int = 1
):
    """Crée une période d'examen de 30 minutes"""
    await interaction.response.defer(ephemeral=True)

    from datetime import datetime, timedelta
    from db_connection import SessionLocal
    from models import ExamPeriod

    try:
        # Parser la date (heure locale)
        start_local = datetime.strptime(start_time, "%Y-%m-%d %H:%M")

        # Convertir en UTC pour la DB (soustraire le décalage)
        start = start_local - timedelta(hours=timezone_offset)
        end = start + timedelta(minutes=30)
        vote_start = start - timedelta(days=1)  # Votes ouverts 24h avant

        # Générer l'ID
        period_id = f"{start.strftime('%Y-%m-%d')}_group{group}"

        # Créer la période
        db = SessionLocal()
        try:
            # Vérifier si une période existe déjà
            existing = db.query(ExamPeriod).filter(ExamPeriod.id == period_id).first()
            if existing:
                # Vérifier si la période est terminée
                now = datetime.now()
                if existing.end_time >= now:
                    # Période encore active, on bloque
                    await interaction.followup.send(
                        f"⚠️ **Une période d'examen ACTIVE existe déjà !**\n\n"
                        f"🆔 ID: `{period_id}`\n"
                        f"📊 Groupe: Niveau {existing.group_number}\n"
                        f"⏰ Début: {existing.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                        f"🏁 Fin: {existing.end_time.strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"💡 Pour créer une nouvelle période:\n"
                        f"• Utilise une date différente, OU\n"
                        f"• Attends la fin de la période actuelle, OU\n"
                        f"• Supprime d'abord l'ancienne avec `/delete_exam_period {period_id}`",
                        ephemeral=True
                    )
                    return
                else:
                    # Période terminée, on la supprime automatiquement
                    print(f"🗑️ Suppression automatique de la période terminée {period_id}")
                    db.delete(existing)
                    db.commit()

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

            # Planifier automatiquement l'application des bonus à la fin de la période
            schedule_bonus_application(bot, period)

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

            # Envoyer le lien d'examen dans le salon "mon-examen" du groupe
            guild = interaction.guild
            if guild:
                # Chercher le salon mon-examen pour ce groupe
                # Format: groupe-X-y où X est le niveau et y une lettre
                # On cherche tous les groupes du niveau concerné
                possible_letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']

                for letter in possible_letters:
                    # Chercher la catégorie du groupe
                    category_name = f"📚 Groupe {group}-{letter.upper()}"
                    category = discord.utils.get(guild.categories, name=category_name)

                    if category:
                        # Chercher le salon mon-examen dans cette catégorie
                        exam_channel = discord.utils.get(category.text_channels, name="📝-mon-examen")

                        if exam_channel:
                            # Créer l'embed pour les étudiants
                            exam_embed = discord.Embed(
                                title="📝 Nouvelle Période d'Examen !",
                                description=f"Une nouvelle période d'examen a été programmée pour le Groupe {group}.",
                                color=discord.Color.blue(),
                                timestamp=datetime.now()
                            )

                            exam_embed.add_field(
                                name="🗳️ Votes",
                                value=f"Du {vote_start.strftime('%d/%m à %H:%M')} au {start.strftime('%d/%m à %H:%M')}",
                                inline=False
                            )

                            exam_embed.add_field(
                                name="📝 Fenêtre d'examen",
                                value=f"Du {start.strftime('%d/%m à %H:%M')} au {end.strftime('%d/%m à %H:%M')}",
                                inline=False
                            )

                            exam_embed.add_field(
                                name="🔗 Lien vers l'examen",
                                value="[Clique ici pour accéder à la page d'examen](http://localhost:5000/exams)\n\n"
                                      "⚠️ N'oublie pas de voter avant de passer l'examen !",
                                inline=False
                            )

                            exam_embed.set_footer(text="Bonne chance ! 💪")

                            await exam_channel.send(embed=exam_embed)
                            print(f"✅ Message envoyé dans {exam_channel.name}")

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
        now = datetime.now()

        # Récupérer seulement les périodes à venir (end_time > now)
        periods = db.query(ExamPeriod).filter(
            ExamPeriod.end_time > now
        ).order_by(ExamPeriod.start_time).all()

        if not periods:
            await interaction.followup.send(
                "📋 Aucune période d'examen à venir",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📋 Périodes d'Examen à Venir",
            color=discord.Color.blue()
        )

        for period in periods:
            # Déterminer le statut en fonction de end_time
            if period.start_time > now:
                status = "🟡 Pas encore commencé"
            elif period.end_time > now:
                status = "🟢 En cours"
            else:
                status = "🔴 Terminée"

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


@bot.tree.command(name="cancel_next_exam", description="[ADMIN] Annuler le prochain examen programmé pour un groupe")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    groupe="Nom du groupe (ex: 1-A, 2-B, Rattrapage Niveau 1)"
)
async def cancel_next_exam(
    interaction: discord.Interaction,
    groupe: str
):
    """Annule le prochain examen programmé pour un groupe donné"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import ExamPeriod
    from datetime import datetime

    db = SessionLocal()
    try:
        now = datetime.now()

        # Récupérer le prochain examen pour ce groupe
        next_exam = db.query(ExamPeriod).filter(
            ExamPeriod.groupe == groupe,
            ExamPeriod.start_time > now
        ).order_by(ExamPeriod.start_time).first()

        if not next_exam:
            await interaction.followup.send(
                f"❌ Aucun examen à venir trouvé pour le groupe `{groupe}`",
                ephemeral=True
            )
            return

        # Afficher les infos avant suppression
        info_msg = (
            f"🗑️ **Examen annulé**\n\n"
            f"🆔 ID: `{next_exam.id}`\n"
            f"📊 Groupe: {next_exam.groupe}\n"
            f"📊 Niveau: {next_exam.group_number}\n"
            f"🗳️ Votes: {next_exam.vote_start_time.strftime('%d/%m/%Y %H:%M')}\n"
            f"⏰ Début: {next_exam.start_time.strftime('%d/%m/%Y %H:%M')}\n"
            f"🏁 Fin: {next_exam.end_time.strftime('%d/%m/%Y %H:%M')}"
        )

        db.delete(next_exam)
        db.commit()

        await interaction.followup.send(info_msg, ephemeral=True)

        # Notifier dans le canal du groupe (optionnel)
        guild = interaction.guild
        if guild:
            # Chercher la catégorie du groupe
            category_name = f"📚 Groupe {groupe}"
            category = discord.utils.get(guild.categories, name=category_name)

            if category:
                # Chercher le salon mon-examen dans cette catégorie
                exam_channel = discord.utils.get(category.text_channels, name="📝-mon-examen")

                if exam_channel:
                    embed = discord.Embed(
                        title="⚠️ Examen Annulé",
                        description=f"L'examen prévu pour le {next_exam.start_time.strftime('%d/%m/%Y à %H:%M')} a été annulé par un administrateur.",
                        color=discord.Color.orange()
                    )
                    await exam_channel.send(embed=embed)
                    print(f"✅ Notification d'annulation envoyée dans {exam_channel.name}")

    finally:
        db.close()


@bot.tree.command(name="actualiser_exams", description="[ADMIN] Actualiser les rôles Discord selon la base de données")
@commands.has_permissions(administrator=True)
async def actualiser_exams(interaction: discord.Interaction):
    """
    Synchronise les rôles Discord avec la base de données
    Applique toutes les promotions qui sont dans la DB mais pas sur Discord
    """
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur

    db = SessionLocal()
    try:
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Commande doit être utilisée sur un serveur", ephemeral=True)
            return

        # Récupérer tous les utilisateurs
        all_users = db.query(Utilisateur).all()

        if not all_users:
            await interaction.followup.send("⚠️ Aucun utilisateur dans la base de données", ephemeral=True)
            return

        # Statistiques
        updated_count = 0
        unchanged_count = 0
        errors = []

        await interaction.followup.send(
            f"🔄 **Actualisation en cours...**\n"
            f"📊 {len(all_users)} utilisateur(s) à vérifier",
            ephemeral=True
        )

        for user_db in all_users:
            try:
                member = guild.get_member(user_db.user_id)

                if not member:
                    errors.append(f"⚠️ {user_db.username} (ID: {user_db.user_id}) - Membre introuvable sur Discord")
                    continue

                # Rôle attendu selon la base de données
                expected_role_name = f"Groupe {user_db.groupe}"
                expected_role = discord.utils.get(guild.roles, name=expected_role_name)

                # Vérifier si le membre a déjà le bon rôle
                if expected_role and expected_role in member.roles:
                    unchanged_count += 1
                    continue

                print(f"\n🔄 Actualisation : {user_db.username}")
                print(f"   Groupe DB: {user_db.groupe}")

                # Retirer tous les anciens rôles de groupe
                for role in member.roles:
                    if role.name.startswith("Groupe "):
                        await member.remove_roles(role)
                        print(f"   ❌ Rôle retiré : {role.name}")

                # Créer ou récupérer le nouveau rôle
                if not expected_role:
                    expected_role = await guild.create_role(
                        name=expected_role_name,
                        color=discord.Color.blue(),
                        mentionable=True,
                        hoist=True  # Afficher séparément à gauche sur Discord
                    )
                    print(f"   ✅ Rôle créé : {expected_role_name}")

                # Ajouter le nouveau rôle
                await member.add_roles(expected_role)
                print(f"   ✅ Rôle ajouté : {expected_role_name}")

                # Créer les salons si nécessaire
                await create_group_channels(guild, user_db.groupe, expected_role)

                # Envoyer un MP de notification
                try:
                    embed = discord.Embed(
                        title="🔄 Rôles Actualisés",
                        description=f"Tes rôles Discord ont été mis à jour !",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="📊 Groupe Actuel",
                        value=f"**{user_db.groupe}** (Niveau {user_db.niveau_actuel})",
                        inline=False
                    )
                    embed.add_field(
                        name="💡 Info",
                        value="Cette actualisation a été effectuée par un administrateur.",
                        inline=False
                    )

                    await member.send(embed=embed)
                    print(f"   ✅ MP envoyé")
                except discord.Forbidden:
                    print(f"   ⚠️ MP bloqués pour {member.name}")

                updated_count += 1

            except Exception as e:
                errors.append(f"❌ {user_db.username} - {str(e)}")
                print(f"❌ Erreur pour {user_db.username}: {e}")

        # Rapport final
        report = discord.Embed(
            title="✅ Actualisation Terminée",
            color=discord.Color.green()
        )

        report.add_field(
            name="📊 Résumé",
            value=f"**{updated_count}** utilisateur(s) actualisé(s)\n"
                  f"**{unchanged_count}** déjà à jour",
            inline=False
        )

        if errors:
            errors_text = "\n".join(errors[:10])  # Max 10 erreurs
            if len(errors) > 10:
                errors_text += f"\n... et {len(errors) - 10} autre(s) erreur(s)"

            report.add_field(
                name="⚠️ Erreurs",
                value=errors_text,
                inline=False
            )

        await interaction.channel.send(embed=report)

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        import traceback
        traceback.print_exc()

    finally:
        db.close()


@bot.tree.command(name="change_group", description="[ADMIN] Modifier le groupe d'un utilisateur")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    user_id="ID Discord de l'utilisateur",
    niveau="Nouveau niveau (1, 2, 3, 4, 5)",
    groupe="Nouvelle lettre du groupe (A, B, C, etc.)"
)
async def change_group(
    interaction: discord.Interaction,
    user_id: str,
    niveau: int,
    groupe: str
):
    """Change le niveau et groupe d'un utilisateur dans la base de données"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur

    db = SessionLocal()
    try:
        # Convertir l'ID en int
        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.followup.send("❌ ID invalide. Utilise un nombre.", ephemeral=True)
            return

        # Valider le niveau
        if niveau not in [1, 2, 3, 4, 5]:
            await interaction.followup.send("❌ Niveau invalide. Utilise 1, 2, 3, 4 ou 5.", ephemeral=True)
            return

        # Valider la lettre du groupe
        groupe_upper = groupe.upper()
        if len(groupe_upper) != 1 or not groupe_upper.isalpha():
            await interaction.followup.send("❌ Groupe invalide. Utilise une seule lettre (A, B, C, etc.)", ephemeral=True)
            return

        # Trouver l'utilisateur
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id_int).first()

        if not user:
            await interaction.followup.send(
                f"❌ Utilisateur avec l'ID `{user_id_int}` introuvable.\n"
                f"Assure-toi qu'il s'est inscrit avec `/register`.",
                ephemeral=True
            )
            return

        # Sauvegarder l'ancien groupe
        old_groupe = user.groupe
        old_niveau = user.niveau_actuel

        # Créer le nouveau groupe
        new_groupe = f"{niveau}-{groupe_upper}"

        # Mettre à jour
        user.niveau_actuel = niveau
        user.groupe = new_groupe

        db.commit()

        # Message de confirmation
        embed = discord.Embed(
            title="✅ Groupe modifié avec succès",
            color=discord.Color.green()
        )

        embed.add_field(name="👤 Utilisateur", value=f"{user.username} (`{user_id_int}`)", inline=False)
        embed.add_field(name="📊 Ancien groupe", value=f"Niveau {old_niveau} - Groupe {old_groupe}", inline=True)
        embed.add_field(name="🆕 Nouveau groupe", value=f"Niveau {niveau} - Groupe {new_groupe}", inline=True)

        embed.set_footer(text="⚠️ N'oublie pas de mettre à jour les rôles Discord manuellement !")

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
