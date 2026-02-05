"""
Bot Discord - Version Ultime
✅ Onboarding via /register avec GroupManager (waiting list + validation temps)
✅ Auto-scheduling d'examens pour les nouveaux groupes
✅ Tâche de fond : traitement des waiting lists (toutes les 5 min)
✅ Notifications automatiques des résultats d'examens
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

    # Démarrer la tâche de traitement des waiting lists
    if not process_waiting_lists_task.is_running():
        process_waiting_lists_task.start()
        print("✅ Tâche waiting list démarrée (vérification toutes les 5 min)")


# ==================== TÂCHE DE FOND : WAITING LIST ====================
@tasks.loop(minutes=5)
async def process_waiting_lists_task():
    """
    Tâche périodique qui vérifie les waiting lists tous les 5 minutes.
    - Si 7+ personnes en attente pour un niveau → crée un nouveau groupe
    - Si des places se libèrent → assigne les utilisateurs en attente
    """
    from db_connection import SessionLocal
    from group_manager import GroupManager
    from models import WaitingList, Utilisateur

    db = SessionLocal()
    try:
        gm = GroupManager(db)

        # Trouver tous les niveaux avec des gens en attente
        niveaux_en_attente = db.query(WaitingList.niveau).distinct().all()

        for (niveau,) in niveaux_en_attente:
            # Traiter la waiting list via GroupManager
            gm.check_and_process_waiting_lists(niveau)

            # Après traitement, vérifier si des utilisateurs ont été assignés
            # et leur envoyer un message + créer les salons Discord
            assigned_users = db.query(Utilisateur).filter(
                Utilisateur.niveau_actuel == niveau,
                Utilisateur.groupe.like(f"{niveau}-%")
            ).all()

            for user in assigned_users:
                # Vérifier si cet utilisateur était en waiting list
                still_waiting = db.query(WaitingList).filter(
                    WaitingList.user_id == user.user_id
                ).first()

                if still_waiting:
                    continue  # Toujours en attente

                # L'utilisateur a été assigné, mettre à jour Discord
                if bot.guilds:
                    guild = bot.guilds[0]
                    member = guild.get_member(user.user_id)

                    if member:
                        try:
                            await finalize_registration(guild, member, user.groupe, user.niveau_actuel)

                            # Envoyer MP de notification
                            embed = discord.Embed(
                                title="🎉 Tu as été assigné à un groupe !",
                                description=(
                                    f"Bonne nouvelle ! Tu as été assigné au **Groupe {user.groupe}**.\n"
                                    "Tu as maintenant accès à tes salons de groupe."
                                ),
                                color=discord.Color.green()
                            )
                            embed.add_field(name="👥 Groupe", value=user.groupe, inline=True)
                            embed.add_field(name="📊 Niveau", value=str(user.niveau_actuel), inline=True)
                            embed.add_field(
                                name="🌐 Liens utiles",
                                value=(
                                    "📚 Cours : http://localhost:5000/courses\n"
                                    "📝 Examens : http://localhost:5000/exams"
                                ),
                                inline=False
                            )
                            await member.send(embed=embed)
                            print(f"✅ Waiting list : {user.username} assigné au groupe {user.groupe}")
                        except Exception as e:
                            print(f"⚠️ Erreur notification waiting list pour {user.user_id}: {e}")

    except Exception as e:
        print(f"❌ Erreur process_waiting_lists_task: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@process_waiting_lists_task.before_loop
async def before_waiting_list_task():
    await bot.wait_until_ready()


@bot.event
async def on_member_join(member: discord.Member):
    """
    Quand quelqu'un rejoint le serveur : assigner le rôle "nouveau"
    L'inscription complète se fait via /register dans #inscriptions
    """
    guild = member.guild

    print(f"\n{'='*50}")
    print(f"👋 NOUVEAU MEMBRE : {member.name} (ID: {member.id})")

    try:
        # Trouver ou créer le rôle "nouveau"
        nouveau_role = discord.utils.get(guild.roles, name="nouveau")

        if not nouveau_role:
            print("⚠️ Rôle 'nouveau' introuvable. Utilise /setup_inscriptions d'abord.")
            return

        # Attribuer le rôle "nouveau"
        await member.add_roles(nouveau_role)
        print(f"✅ Rôle 'nouveau' attribué à {member.name}")

        # Message de bienvenue en MP
        try:
            embed = discord.Embed(
                title="🎓 Bienvenue dans la Formation d'Arabe !",
                description=f"Salut {member.name}, nous sommes ravis de t'accueillir !",
                color=discord.Color.orange()
            )

            embed.add_field(
                name="📝 Pour t'inscrire",
                value=(
                    "1️⃣ Va dans le salon **#inscriptions**\n"
                    "2️⃣ Tape la commande `/register`\n"
                    "3️⃣ Tu seras automatiquement assigné à un groupe !"
                ),
                inline=False
            )

            embed.add_field(
                name="⚠️ Important",
                value="Tu n'auras accès aux autres salons qu'après ton inscription.",
                inline=False
            )

            embed.set_footer(text=f"Ton ID Discord : {member.id}")

            await member.send(embed=embed)
            print(f"✅ Message de bienvenue envoyé")

        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name}")

        print(f"{'='*50}\n")

    except Exception as e:
        print(f"❌ Erreur on_member_join: {e}")
        import traceback
        traceback.print_exc()


async def get_available_group(guild: discord.Guild, niveau: int) -> str:
    """
    Trouve le premier groupe non plein pour un niveau donné
    Limite : 15 membres par groupe
    (Fonction simple de fallback - le flux principal utilise GroupManager)
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


async def auto_schedule_exam_for_new_group(guild: discord.Guild, groupe: str, niveau: int):
    """
    Auto-programme un examen quand un NOUVEAU groupe est créé.
    Les groupes -A sont programmés MANUELLEMENT par l'admin → on les ignore ici.

    Calcul de la date d'examen :
      exam_date = maintenant + temps_minimum + (POURCENTAGE_SUPPLEMENT * temps_minimum)
      Ex: niveau 1 (2j min, 150% supplement) → exam dans 2 + 3 = 5 jours

    La durée de la fenêtre d'examen est copiée depuis le groupe -A du même niveau.
    """
    from db_connection import SessionLocal
    from models import ExamPeriod
    from cohort_config import TEMPS_FORMATION_MINIMUM, POURCENTAGE_SUPPLEMENT_FORMATION, DUREE_EXAMEN_NORMALE

    # Les groupes -A sont programmés manuellement par l'admin
    if '-' in groupe:
        letter = groupe.split('-')[1]
        if letter == 'A':
            print(f"ℹ️ Groupe {groupe} : pas d'auto-scheduling (groupe -A = programmation manuelle)")
            return

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Vérifier si un examen existe déjà pour ce groupe
        existing = db.query(ExamPeriod).filter(
            ExamPeriod.groupe == groupe,
            ExamPeriod.end_time > now
        ).first()

        if existing:
            print(f"ℹ️ Groupe {groupe} a déjà un examen programmé ({existing.id})")
            return

        # Calculer la date d'examen
        temps_minimum = TEMPS_FORMATION_MINIMUM.get(niveau, 3)
        supplement = temps_minimum * POURCENTAGE_SUPPLEMENT_FORMATION
        total_jours = temps_minimum + supplement

        new_start = now + timedelta(days=total_jours)

        # Récupérer la durée depuis l'examen du groupe -A (même niveau)
        group_a_exam = db.query(ExamPeriod).filter(
            ExamPeriod.groupe == f"{niveau}-A",
            ExamPeriod.group_number == niveau
        ).order_by(ExamPeriod.start_time.desc()).first()

        if group_a_exam:
            duration = group_a_exam.end_time - group_a_exam.start_time
        else:
            duration = timedelta(hours=DUREE_EXAMEN_NORMALE)

        new_end = new_start + duration
        vote_start = new_start - timedelta(days=1)

        period_id = f"{new_start.strftime('%Y-%m-%d_%H%M')}_{groupe}"

        period = ExamPeriod(
            id=period_id,
            group_number=niveau,
            groupe=groupe,
            vote_start_time=vote_start,
            start_time=new_start,
            end_time=new_end,
            votes_closed=False,
            bonuses_applied=False
        )
        db.add(period)
        db.commit()

        print(f"✅ Examen AUTO-programmé pour {groupe} :")
        print(f"   📅 Date : {new_start.strftime('%d/%m/%Y %H:%M')} → {new_end.strftime('%d/%m/%Y %H:%M')}")
        print(f"   📐 Calcul : {temps_minimum}j min + {supplement}j supplement ({POURCENTAGE_SUPPLEMENT_FORMATION*100}%) = {total_jours}j")

        # Envoyer notification dans le salon mon-examen du groupe
        category_name = f"📚 Groupe {groupe}"
        category = discord.utils.get(guild.categories, name=category_name)
        if category:
            exam_channel = discord.utils.get(category.text_channels, name="📝-mon-examen")
            if exam_channel:
                exam_embed = discord.Embed(
                    title="📝 Examen Auto-Programmé !",
                    description=f"Un examen a été automatiquement programmé pour le **Groupe {groupe}**.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                exam_embed.add_field(
                    name="🗳️ Votes",
                    value=f"Du {vote_start.strftime('%d/%m à %H:%M')} au {new_start.strftime('%d/%m à %H:%M')}",
                    inline=False
                )
                exam_embed.add_field(
                    name="📝 Fenêtre d'examen",
                    value=f"Du {new_start.strftime('%d/%m à %H:%M')} au {new_end.strftime('%d/%m à %H:%M')}",
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

                # Planifier les bonus
                schedule_bonus_application(bot, period)

    except Exception as e:
        print(f"❌ Erreur auto_schedule_exam: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


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

    # Cacher aussi pour le rôle "nouveau"
    nouveau_role = discord.utils.get(guild.roles, name="nouveau")
    if nouveau_role:
        overwrites[nouveau_role] = discord.PermissionOverwrite(read_messages=False)

    category = await guild.create_category(category_name, overwrites=overwrites)

    # Créer les salons avec le bon format de nommage
    groupe_lower = groupe.lower()

    # Salon ressources (lecture seule pour les membres, bot peut écrire)
    resources_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    if nouveau_role:
        resources_overwrites[nouveau_role] = discord.PermissionOverwrite(read_messages=False)

    resources_channel = await guild.create_text_channel(
        f"📖-ressources",
        category=category,
        overwrites=resources_overwrites
    )

    # Salon entraide
    await guild.create_text_channel(f"💬-entraide", category=category, overwrites=overwrites)
    await guild.create_voice_channel(f"🎙️ Vocal {groupe}", category=category, overwrites=overwrites)

    # Créer le salon "mon-examen" (lecture seule, seul le bot peut écrire)
    exam_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    if nouveau_role:
        exam_overwrites[nouveau_role] = discord.PermissionOverwrite(read_messages=False)

    exam_channel = await guild.create_text_channel(f"📝-mon-examen", category=category, overwrites=exam_overwrites)

    print(f"✅ Catégorie et salons créés pour {groupe}")

    # Envoyer l'embed des cours dans le salon ressources
    courses_embed = discord.Embed(
        title="📚 Cours d'Arabe",
        description="Accède à tous les cours de ton niveau sur notre plateforme en ligne.",
        color=discord.Color.blue()
    )
    courses_embed.add_field(
        name="🔗 Lien des cours",
        value="**http://localhost:5000/courses**",
        inline=False
    )
    courses_embed.add_field(
        name="🆔 Comment accéder ?",
        value=(
            "1. Clique sur le lien ci-dessus\n"
            "2. Entre ton **ID Discord** (visible dans ton profil)\n"
            "3. Tu verras uniquement les cours de ton niveau"
        ),
        inline=False
    )
    courses_embed.add_field(
        name="💡 Astuce",
        value="Tu peux mettre ce lien en favoris, il restera le même peu importe ton niveau !",
        inline=False
    )
    courses_embed.set_footer(text="Bon apprentissage ! 📖")

    await resources_channel.send(embed=courses_embed)

    # Envoyer l'embed des examens dans le salon mon-examen
    exams_embed = discord.Embed(
        title="📝 Examens",
        description="Passe tes examens pour progresser au niveau suivant.",
        color=discord.Color.green()
    )
    exams_embed.add_field(
        name="🔗 Lien des examens",
        value="**http://localhost:5000/exams**",
        inline=False
    )
    exams_embed.add_field(
        name="🆔 Comment passer l'examen ?",
        value=(
            "1. Clique sur le lien ci-dessus\n"
            "2. Entre ton **ID Discord**\n"
            "3. Si un examen est programmé, tu pourras le passer"
        ),
        inline=False
    )
    exams_embed.add_field(
        name="⚠️ Important",
        value="Tu recevras une notification quand un examen sera disponible pour ton groupe.",
        inline=False
    )
    exams_embed.set_footer(text="Bonne chance ! 💪")

    await exam_channel.send(embed=exams_embed)


async def finalize_registration(guild: discord.Guild, member: discord.Member, groupe: str, niveau: int = 1):
    """
    Finalise l'inscription Discord : crée le rôle, assigne, retire 'nouveau', crée les salons.
    Appelé après que GroupManager a validé et enregistré l'utilisateur en DB.
    """
    user_id = member.id
    username = member.name

    # 1. Créer ou récupérer le rôle du groupe
    group_role = discord.utils.get(guild.roles, name=f"Groupe {groupe}")
    if not group_role:
        group_role = await guild.create_role(
            name=f"Groupe {groupe}",
            color=discord.Color.green(),
            mentionable=True,
            hoist=True
        )
        print(f"✅ Rôle créé : {group_role.name}")

    # 2. Attribuer le rôle du groupe
    await member.add_roles(group_role)
    print(f"✅ Rôle {group_role.name} attribué à {username}")

    # 3. Retirer le rôle "nouveau"
    nouveau_role = discord.utils.get(guild.roles, name="nouveau")
    if nouveau_role and nouveau_role in member.roles:
        await member.remove_roles(nouveau_role)
        print(f"✅ Rôle 'nouveau' retiré de {username}")

    # 4. Créer les salons si nécessaire
    await create_group_channels(guild, groupe, group_role)

    # 5. Auto-programmer un examen si d'autres groupes du même niveau en ont
    await auto_schedule_exam_for_new_group(guild, groupe, niveau)


class ConfirmRegistrationView(discord.ui.View):
    """Vue de confirmation quand le temps de formation est insuffisant"""

    def __init__(self, user_id: int, username: str, groupe: str, niveau: int, temps_restant: float, temps_minimum: float):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.username = username
        self.groupe = groupe
        self.niveau = niveau
        self.temps_restant = temps_restant
        self.temps_minimum = temps_minimum

    @discord.ui.button(label="Oui, je m'inscris quand même", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from db_connection import SessionLocal
        from group_manager import GroupManager

        db = SessionLocal()
        try:
            gm = GroupManager(db)
            groupe = gm.confirm_registration_with_insufficient_time(
                self.user_id, self.username, self.niveau, self.groupe
            )

            # Finaliser sur Discord
            guild = interaction.guild
            member = interaction.user
            await finalize_registration(guild, member, groupe, self.niveau)

            embed = discord.Embed(
                title="✅ Inscription réussie !",
                description=f"Bienvenue dans la formation, {member.mention} !",
                color=discord.Color.green()
            )
            embed.add_field(name="👥 Groupe", value=f"**{groupe}**", inline=True)
            embed.add_field(name="📊 Niveau", value=f"**{self.niveau}**", inline=True)
            embed.add_field(name="🆔 Ton ID", value=f"`{self.user_id}`", inline=True)
            embed.add_field(
                name="⚠️ Note",
                value=f"Tu as rejoint avec seulement **{self.temps_restant:.1f}j** avant l'examen "
                      f"(minimum recommandé : {self.temps_minimum}j). Révise bien !",
                inline=False
            )
            embed.add_field(
                name="🌐 Liens utiles",
                value=(
                    f"📚 Cours : http://localhost:5000/courses\n"
                    f"📝 Examens : http://localhost:5000/exams\n"
                    f"Utilise ton ID : `{self.user_id}`"
                ),
                inline=False
            )
            embed.set_footer(text="Tu recevras tes résultats automatiquement en MP après chaque examen !")

            await interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            print(f"❌ Erreur confirmation inscription: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ Une erreur s'est produite. Contacte un administrateur.",
                ephemeral=True
            )
        finally:
            db.close()

    @discord.ui.button(label="Attendre un meilleur moment", style=discord.ButtonStyle.secondary, emoji="⏳")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content="✅ Inscription annulée. Tu pourras retenter `/register` plus tard.",
            embed=None,
            view=None
        )


@bot.tree.command(name="register", description="S'inscrire dans le système")
async def register(interaction: discord.Interaction):
    """
    Inscription complète via GroupManager :
    - Vérifie le temps de formation avant examen
    - Gère la waiting list si nécessaire
    - Assigne un groupe, crée les salons, retire le rôle 'nouveau'
    """
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur
    from group_manager import GroupManager

    guild = interaction.guild
    member = interaction.user
    user_id = member.id
    username = member.name

    db = SessionLocal()

    try:
        gm = GroupManager(db)
        groupe, info = gm.register_user(user_id, username, niveau=1)

        # CAS 1 : Déjà inscrit
        if info['status'] == 'already_registered':
            await interaction.followup.send(
                f"✅ **Déjà inscrit !**\n\n"
                f"**Groupe** : {groupe}\n"
                f"**Niveau** : 1\n"
                f"**ID** : `{user_id}`\n\n"
                f"🌐 Site des cours : http://localhost:5000/courses\n"
                f"🌐 Site des examens : http://localhost:5000/exams",
                ephemeral=True
            )
            return

        # CAS 2 : Inscription directe (groupe disponible, temps suffisant)
        elif info['status'] == 'direct':
            print(f"📌 Groupe attribué à {username} : {groupe}")

            # Finaliser sur Discord (rôle, salons, etc.)
            await finalize_registration(guild, member, groupe, niveau=1)

            embed = discord.Embed(
                title="✅ Inscription réussie !",
                description=f"Bienvenue dans la formation, {member.mention} !",
                color=discord.Color.green()
            )
            embed.add_field(name="👥 Groupe", value=f"**{groupe}**", inline=True)
            embed.add_field(name="📊 Niveau", value="**1**", inline=True)
            embed.add_field(name="🆔 Ton ID", value=f"`{user_id}`", inline=True)
            embed.add_field(
                name="🎯 Prochaines étapes",
                value=(
                    f"1️⃣ Va dans ta catégorie **📚 Groupe {groupe}**\n"
                    "2️⃣ Consulte les ressources et le salon d'entraide\n"
                    "3️⃣ Accède aux cours sur le site\n"
                    "4️⃣ Prépare-toi pour l'examen du Niveau 1"
                ),
                inline=False
            )
            embed.add_field(
                name="🌐 Liens utiles",
                value=(
                    f"📚 Cours : http://localhost:5000/courses\n"
                    f"📝 Examens : http://localhost:5000/exams\n"
                    f"Utilise ton ID : `{user_id}`"
                ),
                inline=False
            )
            embed.set_footer(text="Tu recevras tes résultats automatiquement en MP après chaque examen !")

            await interaction.followup.send(embed=embed, ephemeral=True)

        # CAS 3 : Temps insuffisant avant examen → demander confirmation
        elif info['status'] == 'needs_confirmation':
            temps_restant = info['temps_restant_jours']
            temps_minimum = info['temps_formation_minimum']
            groupe_propose = info['groupe']

            embed = discord.Embed(
                title="⚠️ Temps de formation limité",
                description=(
                    f"Le groupe **{groupe_propose}** a un examen dans **{temps_restant:.1f} jour(s)**.\n"
                    f"Le temps de formation recommandé est de **{temps_minimum} jour(s)**.\n\n"
                    "Tu peux quand même t'inscrire, mais tu auras moins de temps pour te préparer."
                ),
                color=discord.Color.orange()
            )

            view = ConfirmRegistrationView(
                user_id=user_id,
                username=username,
                groupe=groupe_propose,
                niveau=1,
                temps_restant=temps_restant,
                temps_minimum=temps_minimum
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        # CAS 4 : Waiting list (tous les groupes pleins)
        elif info['status'] == 'waiting_list':
            wl_type = info.get('waiting_list_type', 'groupe_plein')

            embed = discord.Embed(
                title="⏳ Ajouté à la liste d'attente",
                description=(
                    "Tous les groupes du Niveau 1 sont actuellement pleins.\n"
                    "Tu as été ajouté à la **liste d'attente**."
                ),
                color=discord.Color.orange()
            )

            if wl_type == 'groupe_plein':
                embed.add_field(
                    name="📋 Que va-t-il se passer ?",
                    value=(
                        "- Dès qu'une place se libère, tu seras automatiquement assigné\n"
                        "- Si **7 personnes ou plus** sont en attente, un nouveau groupe sera créé\n"
                        "- Tu recevras un message quand tu seras assigné"
                    ),
                    inline=False
                )

            embed.set_footer(text="Patience, tu seras bientôt inscrit !")

            await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"❌ Erreur inscription: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(
            "❌ Une erreur s'est produite lors de l'inscription. Contacte un administrateur.",
            ephemeral=True
        )

    finally:
        db.close()


@bot.tree.command(name="clear_db", description="[ADMIN] Vider la base de données")
@app_commands.default_permissions(administrator=True)
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

@bot.tree.command(name="list_users", description="[ADMIN] Liste tous les utilisateurs")
@app_commands.default_permissions(administrator=True)
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
@bot.tree.command(name="create_exam_period", description="[ADMIN] Créer une période d'examen pour un groupe")
@app_commands.default_permissions(administrator=True)
@commands.has_permissions(administrator=True)
@app_commands.describe(
    groupe="Groupe cible (ex: 1-A, 2-B)",
    start_time="Date et heure de début (format: YYYY-MM-DD HH:MM)",
    duration_hours="Durée de la fenêtre d'examen en heures (défaut: 2)"
)
async def create_exam_period(
    interaction: discord.Interaction,
    groupe: str,
    start_time: str,
    duration_hours: int = 2
):
    """
    Crée UNE période d'examen pour UN groupe spécifique.
    Usage principal : programmer manuellement l'examen du groupe -A.
    Les autres groupes (-B, -C, etc.) sont auto-programmés à leur création.
    """
    await interaction.response.defer(ephemeral=True)

    from datetime import datetime, timedelta
    from db_connection import SessionLocal
    from models import ExamPeriod

    try:
        # Valider le format du groupe (ex: "1-A", "2-B")
        if '-' not in groupe or len(groupe.split('-')) != 2:
            await interaction.followup.send(
                "❌ Format de groupe incorrect. Utilise : X-Y (ex: 1-A, 2-B)",
                ephemeral=True
            )
            return

        niveau = int(groupe.split('-')[0])

        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = start + timedelta(hours=duration_hours)
        vote_start = start - timedelta(days=1)

        period_id = f"{start.strftime('%Y-%m-%d_%H%M')}_{groupe}"

        db = SessionLocal()
        try:
            now = datetime.now()

            # Vérifier si une période active existe déjà pour ce groupe
            existing = db.query(ExamPeriod).filter(
                ExamPeriod.groupe == groupe,
                ExamPeriod.end_time >= now
            ).first()

            if existing:
                await interaction.followup.send(
                    f"⚠️ **Une période d'examen ACTIVE existe déjà pour {groupe} !**\n\n"
                    f"🆔 ID: `{existing.id}`\n"
                    f"⏰ Début: {existing.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                    f"🏁 Fin: {existing.end_time.strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"💡 Supprime d'abord l'ancienne avec `/delete_exam_period {existing.id}`",
                    ephemeral=True
                )
                return

            period = ExamPeriod(
                id=period_id,
                group_number=niveau,
                groupe=groupe,
                vote_start_time=vote_start,
                start_time=start,
                end_time=end,
                votes_closed=False,
                bonuses_applied=False
            )

            db.add(period)
            db.commit()

            # Planifier les bonus
            schedule_bonus_application(bot, period)

            # Embed de confirmation
            embed = discord.Embed(
                title="✅ Période d'Examen Créée",
                color=discord.Color.green()
            )
            embed.add_field(name="🆔 ID", value=period_id, inline=False)
            embed.add_field(name="👥 Groupe", value=groupe, inline=True)
            embed.add_field(name="📊 Niveau", value=str(niveau), inline=True)
            embed.add_field(name="🗳️ Votes ouverts", value=vote_start.strftime("%d/%m/%Y %H:%M"), inline=False)
            embed.add_field(name="⏰ Début examen", value=start.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="🏁 Fin examen", value=end.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(
                name="ℹ️ Note",
                value="Les groupes -B, -C, etc. seront auto-programmés à leur création.",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Envoyer notification dans le salon d'examen du groupe
            guild = interaction.guild
            if guild:
                category_name = f"📚 Groupe {groupe}"
                category = discord.utils.get(guild.categories, name=category_name)

                if category:
                    exam_channel = discord.utils.get(category.text_channels, name="📝-mon-examen")

                    if exam_channel:
                        exam_embed = discord.Embed(
                            title="📝 Nouvelle Période d'Examen !",
                            description=f"Une période d'examen a été programmée pour le **Groupe {groupe}**.",
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
                        print(f"✅ Notification envoyée dans {exam_channel.name} ({groupe})")

        finally:
            db.close()

    except ValueError:
        await interaction.followup.send(
            "❌ Format de date incorrect. Utilise : YYYY-MM-DD HH:MM\n"
            "Format de groupe : X-Y (ex: 1-A)",
            ephemeral=True
        )


@bot.tree.command(name="delete_exam_period", description="[ADMIN] Supprimer une période d'examen")
@app_commands.default_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
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


@bot.tree.command(name="actualiser_exams", description="[ADMIN] Actualiser les rôles Discord selon la base de données")
@app_commands.default_permissions(administrator=True)
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
@app_commands.default_permissions(administrator=True)
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


# ==================== COMMANDES UTILITAIRES ADMIN ====================

@bot.tree.command(name="user_info", description="[ADMIN] Voir les informations d'un utilisateur")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    user="L'utilisateur à consulter (mention ou ID)"
)
async def user_info(interaction: discord.Interaction, user: str):
    """Affiche les informations d'un utilisateur"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur, ExamResult

    # Extraire l'ID de la mention ou utiliser directement l'ID
    user_id_str = user.strip()
    if user_id_str.startswith("<@") and user_id_str.endswith(">"):
        user_id_str = user_id_str.replace("<@", "").replace(">", "").replace("!", "")

    try:
        user_id_int = int(user_id_str)
    except ValueError:
        await interaction.followup.send("❌ ID invalide. Utilise une mention (@user) ou un ID numérique.", ephemeral=True)
        return

    db = SessionLocal()
    try:
        user_db = db.query(Utilisateur).filter(Utilisateur.user_id == user_id_int).first()

        if not user_db:
            await interaction.followup.send(
                f"❌ Aucun utilisateur trouvé avec l'ID `{user_id_int}`",
                ephemeral=True
            )
            return

        # Récupérer le membre Discord si possible
        member = interaction.guild.get_member(user_id_int)
        member_name = member.display_name if member else user_db.username

        # Récupérer les résultats d'examen
        exam_results = db.query(ExamResult).filter(
            ExamResult.user_id == user_id_int
        ).order_by(ExamResult.date_passage.desc()).limit(5).all()

        embed = discord.Embed(
            title=f"📋 Informations de {member_name}",
            color=discord.Color.blue()
        )

        embed.add_field(name="🆔 ID Discord", value=f"`{user_db.user_id}`", inline=True)
        embed.add_field(name="👥 Groupe", value=f"**{user_db.groupe}**", inline=True)
        embed.add_field(name="📊 Niveau", value=f"**{user_db.niveau_actuel}**", inline=True)
        embed.add_field(name="📅 Inscrit le", value=user_db.date_inscription.strftime("%d/%m/%Y") if user_db.date_inscription else "N/A", inline=True)
        embed.add_field(name="🎓 Examens réussis", value=f"**{user_db.examens_reussis or 0}**", inline=True)
        embed.add_field(name="🏷️ Cohorte", value=f"`{user_db.cohorte_id}`" if user_db.cohorte_id else "N/A", inline=True)

        # Derniers examens
        if exam_results:
            exams_text = ""
            for result in exam_results:
                status = "✅" if result.reussi else "❌"
                exams_text += f"{status} Niveau {result.niveau} - {result.score}% ({result.date_passage.strftime('%d/%m/%Y')})\n"
            embed.add_field(name="📝 Derniers examens", value=exams_text, inline=False)

        # Statut Discord
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="💻 Statut Discord", value="✅ Sur le serveur", inline=True)
        else:
            embed.add_field(name="💻 Statut Discord", value="❌ Plus sur le serveur", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    finally:
        db.close()


@bot.tree.command(name="delete_user", description="[ADMIN] Supprimer un utilisateur de la base de données")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    user="L'utilisateur à supprimer"
)
async def delete_user(interaction: discord.Interaction, user: discord.Member):
    """Supprime un utilisateur de la base de données"""
    await interaction.response.send_message(
        f"⚠️ **Confirmer la suppression ?**\n\n"
        f"Utilisateur : {user.mention} (`{user.id}`)\n\n"
        f"Cela supprimera :\n"
        f"• Les informations de l'utilisateur\n"
        f"• Ses résultats d'examen\n"
        f"• Ses votes\n\n"
        f"**Cette action est irréversible !**",
        view=ConfirmDeleteUserView(user.id, user.name),
        ephemeral=True
    )


class ConfirmDeleteUserView(discord.ui.View):
    def __init__(self, user_id: int, username: str):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.username = username

    @discord.ui.button(label="✅ Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        from db_connection import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # Supprimer les votes de/pour cet utilisateur
            db.execute(text("DELETE FROM votes WHERE voter_id = :uid OR voted_for_id = :uid"), {"uid": self.user_id})

            # Supprimer les résultats d'examen
            db.execute(text("DELETE FROM exam_results WHERE user_id = :uid"), {"uid": self.user_id})

            # Supprimer l'utilisateur
            result = db.execute(text("DELETE FROM utilisateurs WHERE user_id = :uid"), {"uid": self.user_id})

            db.commit()

            if result.rowcount > 0:
                await interaction.edit_original_response(
                    content=f"✅ **Utilisateur supprimé**\n\n"
                           f"👤 {self.username} (`{self.user_id}`)\n"
                           f"🗑️ Données supprimées de la base",
                    view=None
                )
            else:
                await interaction.edit_original_response(
                    content=f"⚠️ Aucun utilisateur trouvé avec l'ID `{self.user_id}`",
                    view=None
                )

        finally:
            db.close()

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ Suppression annulée",
            view=None
        )


@bot.tree.command(name="group_members", description="[ADMIN] Lister les membres d'un groupe")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    groupe="Le groupe à consulter (ex: 1-A, 2-B)"
)
async def group_members(interaction: discord.Interaction, groupe: str):
    """Liste tous les membres d'un groupe spécifique"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import Utilisateur

    # Normaliser le format du groupe (ex: "1a" -> "1-A")
    groupe_clean = groupe.upper().strip()
    if len(groupe_clean) == 2 and groupe_clean[0].isdigit() and groupe_clean[1].isalpha():
        groupe_clean = f"{groupe_clean[0]}-{groupe_clean[1]}"

    db = SessionLocal()
    try:
        users = db.query(Utilisateur).filter(Utilisateur.groupe == groupe_clean).all()

        if not users:
            await interaction.followup.send(
                f"📭 Aucun membre dans le groupe **{groupe_clean}**",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"👥 Membres du Groupe {groupe_clean}",
            description=f"**{len(users)}** membre(s) au total",
            color=discord.Color.blue()
        )

        # Séparer les membres présents et absents du serveur
        members_present = []
        members_absent = []

        for user_db in users:
            member = interaction.guild.get_member(user_db.user_id)
            if member:
                members_present.append(f"• {member.mention} - Niveau {user_db.niveau_actuel}")
            else:
                members_absent.append(f"• {user_db.username} (`{user_db.user_id}`) - ⚠️ Plus sur le serveur")

        if members_present:
            embed.add_field(
                name=f"✅ Sur le serveur ({len(members_present)})",
                value="\n".join(members_present[:15]) + ("\n..." if len(members_present) > 15 else ""),
                inline=False
            )

        if members_absent:
            embed.add_field(
                name=f"❌ Hors serveur ({len(members_absent)})",
                value="\n".join(members_absent[:10]) + ("\n..." if len(members_absent) > 10 else ""),
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    finally:
        db.close()


@bot.tree.command(name="waiting_list", description="[ADMIN] Afficher la liste d'attente")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    niveau="Filtrer par niveau (optionnel)"
)
async def waiting_list(interaction: discord.Interaction, niveau: int = None):
    """Affiche les personnes en liste d'attente"""
    await interaction.response.defer(ephemeral=True)

    from db_connection import SessionLocal
    from models import WaitingList

    db = SessionLocal()
    try:
        query = db.query(WaitingList).order_by(WaitingList.position)

        if niveau:
            query = query.filter(WaitingList.niveau == niveau)

        waiting_users = query.all()

        if not waiting_users:
            msg = f"📭 Aucune personne en liste d'attente"
            if niveau:
                msg += f" pour le niveau {niveau}"
            await interaction.followup.send(msg, ephemeral=True)
            return

        title = "📋 Liste d'Attente"
        if niveau:
            title += f" - Niveau {niveau}"

        embed = discord.Embed(
            title=title,
            description=f"**{len(waiting_users)}** personne(s) en attente",
            color=discord.Color.orange()
        )

        # Grouper par niveau si pas de filtre
        if not niveau:
            by_level = {}
            for w in waiting_users:
                lvl = w.niveau
                if lvl not in by_level:
                    by_level[lvl] = []
                by_level[lvl].append(w)

            for lvl in sorted(by_level.keys()):
                users_text = ""
                for w in by_level[lvl][:10]:
                    member = interaction.guild.get_member(w.user_id)
                    name = member.mention if member else f"`{w.user_id}`"
                    users_text += f"#{w.position} - {name}\n"
                if len(by_level[lvl]) > 10:
                    users_text += f"... et {len(by_level[lvl]) - 10} autre(s)"

                embed.add_field(
                    name=f"Niveau {lvl} ({len(by_level[lvl])})",
                    value=users_text,
                    inline=False
                )
        else:
            users_text = ""
            for w in waiting_users[:20]:
                member = interaction.guild.get_member(w.user_id)
                name = member.mention if member else f"`{w.user_id}`"
                users_text += f"#{w.position} - {name}\n"
            if len(waiting_users) > 20:
                users_text += f"... et {len(waiting_users) - 20} autre(s)"

            embed.add_field(name="En attente", value=users_text, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    print("🤖 Tâche automatique : Activée (30s)")
    bot.run(token)
