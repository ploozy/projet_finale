"""
Bot Discord - Système de Formation Python
Version 2.0 - Avec Onboarding Automatique et Promotions

Fonctionnalités :
- Onboarding automatique (rôles + salons)
- Gestion dynamique des groupes (15 max par sous-groupe)
- Promotion automatique selon résultats d'examens
- Quiz en MP avec révisions espacées
- Notifications des résultats
"""

import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import json
from datetime import datetime
import asyncio

# Keep-alive et environnement DOIVENT ÊTRE EN PREMIER
from stay_alive import keep_alive
keep_alive()
load_dotenv()

# ===== AUTO-INITIALISATION BASE DE DONNÉES =====
print("🔧 Initialisation automatique de la base de données...")
try:
    from db_connection import engine, Base
    from models import Cohorte, Utilisateur, CalendrierExamen, HistoriqueCohorte, Review, ExamResult
    
    Base.metadata.create_all(engine)
    print("✅ Tables créées/vérifiées")
    
    # Ajouter colonne 'groupe' si nécessaire
    from db_connection import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        check = text("SELECT column_name FROM information_schema.columns WHERE table_name='utilisateurs' AND column_name='groupe'")
        if not db.execute(check).fetchone():
            db.execute(text("ALTER TABLE utilisateurs ADD COLUMN groupe VARCHAR(10) DEFAULT '1-A'"))
            db.commit()
            print("✅ Colonne 'groupe' ajoutée")
        else:
            print("✅ Colonne 'groupe' existe déjà")
    except Exception as e:
        print(f"⚠️ Colonne 'groupe' : {e}")
    finally:
        db.close()
except Exception as e:
    print(f"⚠️ Init DB: {e}")
print("=" * 50)
# ================================================

# Modules de quiz et révisions
from quiz import QuizManager
from scheduler import ReviewScheduler

# Managers PostgreSQL
from cohorte_manager_sql import CohorteManagerSQL
from database_sql import ReviewDatabaseSQL
from exam_result_database_sql import ExamResultDatabaseSQL

# Nouveaux modules
from onboarding import OnboardingManager
from promotion import PromotionManager

token = os.getenv('DISCORD_TOKEN')

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Important pour on_member_join
intents.guilds = True
intents.presences = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Chargement de la config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Initialisation des managers
cohort_manager = CohorteManagerSQL()
review_db = ReviewDatabaseSQL()
exam_db = ExamResultDatabaseSQL()
quiz_manager = QuizManager(bot, review_db, config)
scheduler = ReviewScheduler(bot, review_db, quiz_manager)

# Nouveaux managers
onboarding_manager = OnboardingManager(bot)
promotion_manager = PromotionManager(bot)


@bot.event
async def on_ready():
    """Appelé quand le bot est connecté et prêt"""
    print(f'✅ Bot connecté en tant que {bot.user}')
    print(f'📊 Connecté à {len(bot.guilds)} serveur(s)')
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commande(s) slash synchronisée(s)')
    except Exception as e:
        print(f'❌ Erreur synchronisation commandes: {e}')
    
    # Démarrer le scheduler de révisions (SI BESOIN)
    try:
        scheduler.start()
        print('⏰ Scheduler de révisions initialisé')
    except Exception as e:
        print(f'⚠️ Scheduler non disponible: {e}')


@bot.event
async def on_member_join(member: discord.Member):
    """
    ÉVÉNEMENT AUTOMATIQUE : Nouveau membre rejoint le serveur
    
    1. Attribution rôle automatique (Groupe X-Y)
    2. Création des salons si nécessaire
    3. Enregistrement en base de données
    4. Message de bienvenue en MP
    """
    print(f"👋 Nouveau membre : {member.name} ({member.id})")
    
    try:
        await onboarding_manager.on_member_join(member)
        print(f"✅ Onboarding réussi pour {member.name}")
    except Exception as e:
        print(f"❌ Erreur onboarding {member.name}: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="register", description="S'enregistrer dans le système")
async def register(interaction: discord.Interaction):
    """
    Commande pour s'enregistrer manuellement dans le système
    Utile si l'onboarding automatique a échoué
    """
    # RÉPONDRE IMMÉDIATEMENT (dans les 3 secondes)
    await interaction.response.send_message(
        "🔄 Vérification de ton inscription...",
        ephemeral=True
    )
    
    db = None
    try:
        from db_connection import SessionLocal
        from models import Utilisateur
        
        db = SessionLocal()
        
        print(f"🔍 /register demandé par {interaction.user.name} (ID: {interaction.user.id})")
        
        # Vérifier si déjà enregistré
        existing = db.query(Utilisateur).filter(
            Utilisateur.user_id == interaction.user.id
        ).first()
        
        if existing:
            print(f"✅ {interaction.user.name} déjà enregistré (Groupe {existing.groupe})")
            await interaction.edit_original_response(
                content=f"✅ **Tu es déjà enregistré !**\n\n"
                f"📌 **Groupe** : {existing.groupe}\n"
                f"📊 **Niveau** : {existing.niveau_actuel}\n"
                f"🆔 **ID Discord** : `{interaction.user.id}`\n\n"
                f"🌐 Passe ton examen sur : https://site-fromation.onrender.com/exams"
            )
            return
        
        # Pas encore enregistré
        print(f"⏳ Inscription de {interaction.user.name}...")
        
        # Mettre à jour le message
        await interaction.edit_original_response(
            content="⏳ Création de ton compte..."
        )
        
        # Récupérer le Member depuis le serveur
        member = interaction.guild.get_member(interaction.user.id)
        
        if not member:
            print(f"❌ Member introuvable pour {interaction.user.id}")
            await interaction.edit_original_response(
                content="❌ Impossible de te trouver sur le serveur."
            )
            return
        
        # Lancer le processus d'onboarding
        await onboarding_manager.on_member_join(member)
        
        # Attendre 2 secondes que PostgreSQL soit mis à jour
        await asyncio.sleep(2)
        
        # Vérifier que ça a fonctionné
        db.expire_all()  # Rafraîchir la session
        user = db.query(Utilisateur).filter(
            Utilisateur.user_id == interaction.user.id
        ).first()
        
        if user:
            print(f"✅ {interaction.user.name} enregistré avec succès (Groupe {user.groupe})")
            await interaction.edit_original_response(
                content=f"✅ **Inscription réussie !**\n\n"
                f"📌 **Groupe** : {user.groupe}\n"
                f"📊 **Niveau** : {user.niveau_actuel}\n"
                f"🆔 **ID Discord** : `{interaction.user.id}`\n\n"
                f"✨ Tu as maintenant accès à tes salons !\n"
                f"🌐 Passe ton examen sur : https://site-fromation.onrender.com/exams"
            )
        else:
            print(f"⚠️ {interaction.user.name} - Rôle attribué mais pas trouvé en DB")
            await interaction.edit_original_response(
                content=f"⚠️ **Inscription partiellement réussie**\n\n"
                f"Tu as reçu ton rôle Discord mais une erreur s'est produite.\n"
                f"🆔 **Ton ID** : `{interaction.user.id}`\n\n"
                f"Essaie d'aller sur le site web avec ton ID.\n"
                f"Si ça ne marche pas, contacte un admin."
            )
        
    except Exception as e:
        print(f"❌ Erreur /register pour {interaction.user.name}: {e}")
        import traceback
        traceback.print_exc()
        
        await interaction.edit_original_response(
            content=f"❌ **Erreur**\n\n"
            f"```{str(e)}```\n\n"
            f"🆔 **Ton ID** : `{interaction.user.id}`\n"
            f"Contacte un administrateur avec cette erreur."
        )
    
    finally:
        if db:
            db.close()


@bot.tree.command(name="check_exam_results", description="[ADMIN] Vérifier et notifier les résultats d'examens web")
@commands.has_permissions(administrator=True)
async def check_exam_results(interaction: discord.Interaction):
    """
    Commande ADMIN pour traiter les résultats d'examens du site web
    
    Pour chaque résultat non notifié :
    - Si réussi (≥70%) : Promotion au niveau suivant + nouveau groupe
    - Si échoué : Reste dans le groupe actuel + notification
    """
    await interaction.response.defer()
    
    try:
        print(f"🔍 /check_exam_results lancé par {interaction.user.name}")
        
        guild = interaction.guild
        result_message = await promotion_manager.check_and_notify_results(guild)
        
        await interaction.followup.send(result_message)
        
    except Exception as e:
        print(f"❌ Erreur check_exam_results: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(f"❌ Erreur : {e}")


@bot.tree.command(name="stats", description="[ADMIN] Afficher les statistiques des groupes")
@commands.has_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    """
    Affiche les statistiques des groupes :
    - Nombre de membres par groupe
    - Répartition par niveau
    - Taux de réussite
    """
    await interaction.response.defer()
    
    try:
        guild = interaction.guild
        
        embed = discord.Embed(
            title="📊 Statistiques des Groupes",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Compter les membres par rôle
        groups_stats = {}
        for role in guild.roles:
            if role.name.startswith("Groupe "):
                member_count = len(role.members)
                if member_count > 0:
                    groups_stats[role.name] = member_count
        
        if groups_stats:
            # Trier par nom de groupe
            sorted_groups = sorted(groups_stats.items())
            
            stats_text = ""
            for group_name, count in sorted_groups:
                bar = "█" * count + "░" * (15 - count) if count <= 15 else "█" * 15
                stats_text += f"**{group_name}** : {count}/15 membres\n`{bar}`\n\n"
            
            embed.add_field(
                name="👥 Répartition par Groupe",
                value=stats_text or "Aucun groupe actif",
                inline=False
            )
        else:
            embed.add_field(
                name="👥 Répartition par Groupe",
                value="Aucun groupe actif pour le moment",
                inline=False
            )
        
        # Statistiques globales
        total_members = sum(groups_stats.values()) if groups_stats else 0
        total_groups = len(groups_stats)
        
        embed.add_field(
            name="📈 Statistiques Globales",
            value=f"**Total membres** : {total_members}\n"
                  f"**Groupes actifs** : {total_groups}\n"
                  f"**Moyenne par groupe** : {total_members/total_groups if total_groups > 0 else 0:.1f}",
            inline=False
        )
        
        embed.set_footer(text=f"Serveur: {guild.name}")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}")
        print(f"❌ Erreur stats: {e}")


@bot.tree.command(name="manual_promote", description="[ADMIN] Promouvoir manuellement un utilisateur")
@commands.has_permissions(administrator=True)
async def manual_promote(interaction: discord.Interaction, member: discord.Member):
    """
    Commande ADMIN pour promouvoir manuellement un utilisateur
    Utile pour corriger des erreurs ou faire des promotions exceptionnelles
    """
    await interaction.response.defer()
    
    db = None
    try:
        from db_connection import SessionLocal
        from models import Utilisateur
        
        db = SessionLocal()
        
        # Récupérer l'utilisateur de la DB
        user_db = db.query(Utilisateur).filter(
            Utilisateur.user_id == member.id
        ).first()
        
        if not user_db:
            await interaction.followup.send(f"❌ {member.mention} n'est pas enregistré dans la base de données.")
            return
        
        old_niveau = user_db.niveau_actuel
        old_groupe = user_db.groupe
        
        if old_niveau >= 5:
            await interaction.followup.send(f"❌ {member.mention} est déjà au niveau maximum (5).")
            return
        
        # Utiliser le système de promotion normal
        new_niveau = old_niveau + 1
        new_groupe = await onboarding_manager._get_available_group(interaction.guild, new_niveau)
        
        # Mettre à jour la DB
        user_db.niveau_actuel = new_niveau
        user_db.groupe = new_groupe
        user_db.examens_reussis += 1
        db.commit()
        
        # Changer les rôles Discord
        old_role = discord.utils.get(interaction.guild.roles, name=f"Groupe {old_groupe}")
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)
        
        new_role = await onboarding_manager._get_or_create_role(interaction.guild, new_groupe)
        await member.add_roles(new_role)
        
        # Créer les salons si nécessaire
        await onboarding_manager._create_group_channels(interaction.guild, new_groupe, new_role)
        
        # Notification
        try:
            await member.send(
                f"🎉 **Promotion Manuelle**\n\n"
                f"Tu as été promu manuellement par un administrateur !\n"
                f"**{old_groupe}** → **{new_groupe}**\n\n"
                f"Tu as maintenant accès aux salons du Groupe {new_groupe}.\n"
                f"Bon courage pour la suite ! 💪"
            )
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name}")
        
        await interaction.followup.send(
            f"✅ {member.mention} a été promu manuellement !\n"
            f"**{old_groupe}** → **{new_groupe}**"
        )
        
        print(f"✅ Promotion manuelle : {member.name} {old_groupe} → {new_groupe}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}")
        print(f"❌ Erreur manual_promote: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if db:
            db.close()


@bot.tree.command(name="my_info", description="Afficher tes informations de progression")
async def my_info(interaction: discord.Interaction):
    """
    Affiche les informations de l'utilisateur :
    - Groupe actuel
    - Niveau
    - Examens réussis
    - Prochaines étapes
    """
    await interaction.response.defer(ephemeral=True)
    
    db = None
    try:
        from db_connection import SessionLocal
        from models import Utilisateur
        
        db = SessionLocal()
        
        user_db = db.query(Utilisateur).filter(
            Utilisateur.user_id == interaction.user.id
        ).first()
        
        if not user_db:
            await interaction.followup.send(
                "❌ Tu n'es pas encore enregistré dans le système.\n"
                "Utilise la commande `/register` pour t'inscrire.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Tes Informations",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.set_author(
            name=interaction.user.name,
            icon_url=interaction.user.display_avatar.url
        )
        
        embed.add_field(
            name="👥 Ton Groupe",
            value=f"**Groupe {user_db.groupe}**",
            inline=True
        )
        
        embed.add_field(
            name="📊 Niveau Actuel",
            value=f"**Niveau {user_db.niveau_actuel}**",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Examens Réussis",
            value=f"**{user_db.examens_reussis}**",
            inline=True
        )
        
        embed.add_field(
            name="📅 Inscrit Depuis",
            value=f"{user_db.date_inscription.strftime('%d/%m/%Y')}",
            inline=True
        )
        
        embed.add_field(
            name="🏆 Cohorte",
            value=f"**{user_db.cohorte_id}**",
            inline=True
        )
        
        embed.add_field(
            name="🆔 ID Discord",
            value=f"`{interaction.user.id}`",
            inline=True
        )
        
        # Progression
        progress = (user_db.niveau_actuel / 5) * 100
        progress_bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        
        embed.add_field(
            name="📈 Progression Globale",
            value=f"`{progress_bar}` {progress:.0f}%\n"
                  f"Niveau {user_db.niveau_actuel}/5",
            inline=False
        )
        
        # Prochaines étapes
        next_steps = "• Consulte les ressources dans ton salon\n"
        next_steps += f"• Prépare-toi pour l'examen du Niveau {user_db.niveau_actuel}\n"
        next_steps += "• Demande de l'aide dans #entraide si besoin\n"
        next_steps += f"• Passe ton examen sur : https://site-fromation.onrender.com/exams\n"
        next_steps += f"• Utilise ton ID : `{interaction.user.id}`"
        
        embed.add_field(
            name="🎯 Prochaines Étapes",
            value=next_steps,
            inline=False
        )
        
        embed.set_footer(text=f"ID Discord: {interaction.user.id}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        print(f"❌ Erreur my_info: {e}")
    
    finally:
        if db:
            db.close()


# Gestion des erreurs globales
@bot.event
async def on_command_error(ctx, error):
    """Gestion des erreurs de commandes"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas les permissions nécessaires pour utiliser cette commande.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignorer les commandes inconnues
    else:
        print(f"❌ Erreur commande: {error}")


# Lancement du bot
if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    bot.run(token)
