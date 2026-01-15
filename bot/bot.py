"""
Bot Discord - Version Ultra-Simplifiée
Fonctionne à 100% sans complexité
"""

import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime
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
    
    # Créer toutes les tables
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


@bot.event
async def on_ready():
    """Appelé quand le bot est connecté"""
    print(f'✅ Bot connecté : {bot.user}')
    print(f'📊 Serveurs : {len(bot.guilds)}')
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ Commandes synchronisées : {len(synced)}')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')


@bot.tree.command(name="register", description="S'inscrire dans le système")
async def register(interaction: discord.Interaction):
    """
    COMMANDE ULTRA-SIMPLE QUI FONCTIONNE
    Écrit DIRECTEMENT dans PostgreSQL sans passer par des managers
    """
    await interaction.response.send_message("🔄 Inscription en cours...", ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur, Cohorte
    from sqlalchemy import text
    
    db = SessionLocal()
    
    try:
        user_id = interaction.user.id
        username = interaction.user.name
        
        print(f"\n{'='*50}")
        print(f"🔍 REGISTER demandé par {username} (ID: {user_id})")
        print(f"{'='*50}")
        
        # 1. Vérifier si existe déjà
        existing = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if existing:
            print(f"✅ Utilisateur existe déjà : Groupe {existing.groupe}, Niveau {existing.niveau_actuel}")
            await interaction.edit_original_response(
                content=f"✅ **Déjà inscrit !**\n\n"
                       f"**Groupe** : {existing.groupe}\n"
                       f"**Niveau** : {existing.niveau_actuel}\n"
                       f"**ID** : `{user_id}`\n\n"
                       f"🌐 Site : https://site-fromation.onrender.com/exams"
            )
            return
        
        # 2. Déterminer le groupe
        # Chercher le premier groupe non plein
        groupe = "1-A"  # Par défaut
        
        for letter in ['A', 'B', 'C', 'D', 'E']:
            test_groupe = f"1-{letter}"
            role = discord.utils.get(interaction.guild.roles, name=f"Groupe {test_groupe}")
            
            if role is None or len(role.members) < 15:
                groupe = test_groupe
                print(f"📌 Groupe attribué : {groupe}")
                break
        
        # 3. Créer ou récupérer la cohorte JAN26-A
        now = datetime.now()
        month = now.strftime("%b").upper()
        year = str(now.year)[-2:]
        cohorte_id = f"{month}{year}-A"
        
        cohorte = db.query(Cohorte).filter(Cohorte.id == cohorte_id).first()
        if not cohorte:
            from datetime import timedelta
            cohorte = Cohorte(
                id=cohorte_id,
                date_creation=now,
                date_premier_examen=now + timedelta(days=14),
                niveau_actuel=1,
                statut='active'
            )
            db.add(cohorte)
            db.flush()
            print(f"✅ Cohorte créée : {cohorte_id}")
        
        # 4. INSÉRER l'utilisateur DIRECTEMENT
        new_user = Utilisateur(
            user_id=user_id,
            username=username,
            cohorte_id=cohorte_id,
            niveau_actuel=1,
            groupe=groupe,
            examens_reussis=0,
            date_inscription=now
        )
        
        db.add(new_user)
        db.commit()
        
        print(f"✅ UTILISATEUR AJOUTÉ EN BASE DE DONNÉES")
        print(f"   - ID: {user_id}")
        print(f"   - Username: {username}")
        print(f"   - Niveau: 1")
        print(f"   - Groupe: {groupe}")
        print(f"   - Cohorte: {cohorte_id}")
        
        # 5. Attribuer le rôle Discord
        role = discord.utils.get(interaction.guild.roles, name=f"Groupe {groupe}")
        if not role:
            # Créer le rôle
            role = await interaction.guild.create_role(
                name=f"Groupe {groupe}",
                color=discord.Color.green(),
                mentionable=True
            )
            print(f"✅ Rôle créé : {role.name}")
        
        member = interaction.guild.get_member(user_id)
        if member:
            await member.add_roles(role)
            print(f"✅ Rôle attribué à {username}")
        
        # 6. Vérifier que ça a bien été enregistré
        await asyncio.sleep(1)
        
        verification = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if verification:
            print(f"✅ VÉRIFICATION OK : Utilisateur bien en base")
            print(f"   Groupe stocké : {verification.groupe}")
            print(f"   Niveau stocké : {verification.niveau_actuel}")
            
            await interaction.edit_original_response(
                content=f"✅ **Inscription réussie !**\n\n"
                       f"**Groupe** : {verification.groupe}\n"
                       f"**Niveau** : {verification.niveau_actuel}\n"
                       f"**ID** : `{user_id}`\n\n"
                       f"🌐 Va sur : https://site-fromation.onrender.com/exams\n"
                       f"Entre ton ID : `{user_id}`"
            )
        else:
            print(f"❌ VÉRIFICATION ÉCHOUÉE : Utilisateur pas trouvé après insertion")
            await interaction.edit_original_response(
                content=f"⚠️ **Erreur mystérieuse**\n\n"
                       f"L'utilisateur a été inséré mais n'est pas retrouvé.\n"
                       f"**Ton ID** : `{user_id}`\n\n"
                       f"Contacte un admin."
            )
        
        print(f"{'='*50}\n")
        
    except Exception as e:
        db.rollback()
        print(f"❌ ERREUR REGISTER : {e}")
        import traceback
        traceback.print_exc()
        
        await interaction.edit_original_response(
            content=f"❌ **Erreur**\n```{str(e)}```\n**Ton ID** : `{user_id}`"
        )
    
    finally:
        db.close()


@bot.tree.command(name="clear_db", description="[ADMIN] Vider complètement la base de données")
@commands.has_permissions(administrator=True)
async def clear_db(interaction: discord.Interaction):
    """
    COMMANDE ADMIN : Vide TOUTE la base de données
    ATTENTION : Irréversible !
    """
    await interaction.response.send_message(
        "⚠️ **ATTENTION** ⚠️\n\n"
        "Tu es sur le point de **SUPPRIMER TOUTES LES DONNÉES** !\n"
        "Clique sur le bouton pour confirmer.",
        view=ConfirmClearView(),
        ephemeral=True
    )


class ConfirmClearView(discord.ui.View):
    """Bouton de confirmation pour vider la DB"""
    
    def __init__(self):
        super().__init__(timeout=30)
    
    @discord.ui.button(label="✅ OUI, VIDER LA BASE", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        from db_connection import SessionLocal
        from models import Utilisateur, ExamResult, Cohorte
        from sqlalchemy import text
        
        db = SessionLocal()
        
        try:
            print(f"\n🔥 CLEAR_DB demandé par {interaction.user.name}")
            
            # Compter avant suppression
            user_count = db.query(Utilisateur).count()
            result_count = db.query(ExamResult).count()
            
            # SUPPRIMER TOUT
            db.execute(text("DELETE FROM exam_results"))
            db.execute(text("DELETE FROM utilisateurs"))
            db.execute(text("DELETE FROM cohortes"))
            db.commit()
            
            print(f"✅ BASE VIDÉE : {user_count} utilisateurs, {result_count} résultats supprimés")
            
            await interaction.edit_original_response(
                content=f"✅ **Base de données vidée !**\n\n"
                       f"- {user_count} utilisateurs supprimés\n"
                       f"- {result_count} résultats supprimés\n\n"
                       f"La base est maintenant vide.",
                view=None
            )
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur clear_db: {e}")
            await interaction.edit_original_response(
                content=f"❌ Erreur : {e}",
                view=None
            )
        
        finally:
            db.close()
    
    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ Opération annulée. Aucune donnée supprimée.",
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
            await interaction.followup.send(
                "❌ Tu n'es pas inscrit. Utilise `/register`",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Tes Informations",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="👥 Groupe", value=f"**{user.groupe}**", inline=True)
        embed.add_field(name="📊 Niveau", value=f"**{user.niveau_actuel}**", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{user.user_id}`", inline=True)
        embed.add_field(
            name="🌐 Lien Examen",
            value=f"https://site-fromation.onrender.com/exams\nUtilise ton ID : `{user.user_id}`",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()


@bot.tree.command(name="list_users", description="[ADMIN] Liste tous les utilisateurs")
@commands.has_permissions(administrator=True)
async def list_users(interaction: discord.Interaction):
    """Liste tous les utilisateurs en base"""
    await interaction.response.defer(ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur
    
    db = SessionLocal()
    
    try:
        users = db.query(Utilisateur).all()
        
        if not users:
            await interaction.followup.send("📭 Aucun utilisateur en base", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"👥 Utilisateurs ({len(users)})",
            color=discord.Color.blue()
        )
        
        for user in users[:25]:  # Max 25 pour ne pas dépasser la limite Discord
            embed.add_field(
                name=f"{user.username}",
                value=f"ID: `{user.user_id}`\nGroupe: {user.groupe}\nNiveau: {user.niveau_actuel}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    bot.run(token)
