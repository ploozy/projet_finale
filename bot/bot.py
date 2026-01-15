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


@bot.tree.command(name="manu")
