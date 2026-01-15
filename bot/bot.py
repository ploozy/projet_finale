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

# Modules de quiz et révisions
from quiz import QuizManager
from scheduler import ReviewScheduler
from stay_alive import keep_alive

# Managers PostgreSQL
from cohorte_manager_sql import CohorteManagerSQL
from database_sql import ReviewDatabaseSQL
from exam_result_database_sql import ExamResultDatabaseSQL

# Nouveaux modules
from onboarding import OnboardingManager
from promotion import PromotionManager

print("🔧 Initialisation du système...")

try:
    print("📦 Vérification de la base de données...")
    from init_db import init_database
    init_database()
except Exception as e:
    print(f"⚠️ Erreur init DB: {e}")

try:
    print("📦 Vérification de la colonne 'groupe'...")
    from add_groupe_column import add_groupe_column
    add_groupe_column()
except Exception as e:
    print(f"⚠️ Erreur migration: {e}")

print("✅ Initialisation terminée")

# Keep-alive et environnement
keep_alive()
load_dotenv()
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
    
    # Démarrer le scheduler de révisions
    bot.loop.create_task(scheduler.start())
    print('⏰ Scheduler de révisions initialisé')


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
    except Exception as e:
        print(f"❌ Erreur onboarding {member.name}: {e}")


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
        guild = interaction.guild
        result_message = await promotion_manager.check_and_notify_results(guild)
        
        await interaction.followup.send(result_message)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}")
        print(f"❌ Erreur check_exam_results: {e}")


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
                bar = "█" * count + "░" * (15 - count)
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
        await member.send(
            f"🎉 **Promotion Manuelle**\n\n"
            f"Tu as été promu manuellement par un administrateur !\n"
            f"**{old_groupe}** → **{new_groupe}**\n\n"
            f"Tu as maintenant accès aux salons du Groupe {new_groupe}.\n"
            f"Bon courage pour la suite ! 💪"
        )
        
        await interaction.followup.send(
            f"✅ {member.mention} a été promu manuellement !\n"
            f"**{old_groupe}** → **{new_groupe}**"
        )
        
        db.close()
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}")
        print(f"❌ Erreur manual_promote: {e}")


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
                "Cela devrait se faire automatiquement quand tu as rejoint le serveur.",
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
        next_steps += "• Passe ton examen sur le site web avec ton ID Discord"
        
        embed.add_field(
            name="🎯 Prochaines Étapes",
            value=next_steps,
            inline=False
        )
        
        embed.set_footer(text=f"ID Discord: {interaction.user.id}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        db.close()
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        print(f"❌ Erreur my_info: {e}")


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
