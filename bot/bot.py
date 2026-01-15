"""
Bot Discord - Version Finale Complète
1. Onboarding automatique (on_member_join)
2. Sync rôles Discord après promotion sur site web
"""

import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import calendar

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


@bot.event
async def on_member_join(member: discord.Member):
    """
    ONBOARDING AUTOMATIQUE
    Quand quelqu'un rejoint le serveur :
    1. Lui attribuer le rôle "Groupe 1-A" (ou 1-B si 1-A plein)
    2. Créer les salons si nécessaire
    3. L'enregistrer en base de données
    4. Lui envoyer un message de bienvenue
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
                    f"4️⃣ Passe ton examen sur le site web avec ton ID : `{member.id}`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🌐 Lien du Site",
                value="https://site-fromation.onrender.com/exams",
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
    Ex: Si 1-A est plein (15 membres), retourne 1-B
    """
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    
    for letter in letters:
        groupe_name = f"{niveau}-{letter}"
        role = discord.utils.get(guild.roles, name=f"Groupe {groupe_name}")
        
        if role is None:
            # Le rôle n'existe pas, ce groupe est disponible
            return groupe_name
        
        member_count = len(role.members)
        
        if member_count < 15:
            # Le groupe a de la place
            return groupe_name
    
    # Par défaut (ne devrait jamais arriver)
    return f"{niveau}-A"


async def create_group_channels(guild: discord.Guild, groupe: str, role: discord.Role):
    """
    Crée une catégorie et des salons pour un groupe
    Ex: Groupe 1-A → Catégorie "📚 Groupe 1-A" avec salons dédiés
    """
    category_name = f"📚 Groupe {groupe}"
    
    # Vérifier si la catégorie existe déjà
    category = discord.utils.get(guild.categories, name=category_name)
    
    if category:
        return  # Les salons existent déjà
    
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
    """
    COMMANDE MANUELLE D'INSCRIPTION
    (au cas où l'onboarding automatique aurait échoué)
    """
    await interaction.response.send_message("🔄 Inscription en cours...", ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur, Cohorte
    
    db = SessionLocal()
    
    try:
        user_id = interaction.user.id
        username = interaction.user.name
        
        print(f"\n{'='*50}")
        print(f"🔍 /register par {username} (ID: {user_id})")
        
        # Vérifier si existe déjà
        existing = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if existing:
            print(f"✅ Déjà enregistré")
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
                           f"🌐 Va sur : https://site-fromation.onrender.com/exams"
                )
            else:
                await interaction.edit_original_response(
                    content=f"⚠️ Erreur d'inscription. Contacte un admin."
                )
        
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"❌ Erreur /register: {e}")
        import traceback
        traceback.print_exc()
        await interaction.edit_original_response(
            content=f"❌ Erreur : {e}"
        )
    
    finally:
        db.close()


@bot.tree.command(name="check_exam_results", description="[ADMIN] Vérifier les résultats et sync les rôles")
@commands.has_permissions(administrator=True)
async def check_exam_results(interaction: discord.Interaction):
    """
    COMMANDE ADMIN COMPLÈTE
    1. Lit les résultats d'examens sur le site web
    2. Change les rôles Discord selon le résultat
    3. Envoie un MP à chaque utilisateur
    """
    await interaction.response.defer()
    
    from db_connection import SessionLocal
    from models import ExamResult, Utilisateur
    
    db = SessionLocal()
    
    try:
        # Récupérer les résultats non notifiés
        results = db.query(ExamResult).filter(ExamResult.notified == False).all()
        
        if not results:
            await interaction.followup.send("📭 Aucun nouveau résultat")
            return
        
        print(f"\n{'='*50}")
        print(f"🔔 CHECK_EXAM_RESULTS : {len(results)} résultats")
        
        notified_count = 0
        promoted_count = 0
        
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
                member = interaction.guild.get_member(result.user_id)
                
                if not member:
                    print(f"⚠️ Member {result.user_id} pas sur Discord")
                    continue
                
                old_groupe = user_db.groupe
                new_groupe = user_db.groupe  # Par défaut, reste le même
                
                # SI RÉUSSI → Changer le rôle Discord
                if result.passed and user_db.niveau_actuel <= 5:
                    # Récupérer le nouveau groupe depuis la DB (déjà mis à jour par le site web)
                    new_groupe = user_db.groupe
                    
                    print(f"🎉 {member.name} : {old_groupe} → {new_groupe}")
                    
                    # Retirer l'ancien rôle
                    old_role = discord.utils.get(interaction.guild.roles, name=f"Groupe {old_groupe}")
                    if old_role and old_role in member.roles:
                        await member.remove_roles(old_role)
                        print(f"   ❌ Rôle retiré : {old_role.name}")
                    
                    # Ajouter le nouveau rôle (ou le créer)
                    new_role = discord.utils.get(interaction.guild.roles, name=f"Groupe {new_groupe}")
                    if not new_role:
                        new_role = await interaction.guild.create_role(
                            name=f"Groupe {new_groupe}",
                            color=discord.Color.blue(),
                            mentionable=True
                        )
                        print(f"   ✅ Rôle créé : {new_role.name}")
                    
                    await member.add_roles(new_role)
                    print(f"   ✅ Rôle ajouté : {new_role.name}")
                    
                    # Créer les salons si nécessaire
                    await create_group_channels(interaction.guild, new_groupe, new_role)
                    
                    promoted_count += 1
                
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
                
                await member.send(message)
                
                # Marquer comme notifié
                result.notified = True
                db.commit()
                
                notified_count += 1
                print(f"✅ Notifié : {member.name}")
                
            except discord.Forbidden:
                print(f"⚠️ MP impossible pour {member.name}")
            except Exception as e:
                print(f"❌ Erreur pour {result.user_id}: {e}")
        
        print(f"{'='*50}\n")
        
        await interaction.followup.send(
            f"✅ **Traitement terminé !**\n\n"
            f"📨 {notified_count} notifications envoyées\n"
            f"🎉 {promoted_count} promotions effectuées\n"
            f"🔄 Rôles Discord mis à jour"
        )
    
    finally:
        db.close()


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


if __name__ == "__main__":
    print("🚀 Démarrage du bot...")
    bot.run(token)
