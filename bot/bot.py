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


@bot.tree.command(name="send_course", description="[ADMIN] Envoyer un lien vers un cours")
@commands.has_permissions(administrator=True)
async def send_course(
    interaction: discord.Interaction,
    course_id: str,
    channel: discord.TextChannel
):
    """
    Envoie un lien vers la page du cours sur le site web
    
    Args:
        course_id: ID du cours (ex: "variables", "loops")
        channel: Salon où envoyer le lien
    """
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Créer l'embed
        embed = discord.Embed(
            title=f"📚 Cours : {course_id.title()}",
            description=f"Accède au cours en ligne !",
            color=discord.Color.blue()
        )
        
        # URL vers la page des cours
        course_url = f"https://site-fromation.onrender.com/course/{course_id}"
        
        embed.add_field(
            name="🌐 Lien du cours",
            value=f"[Cliquez ici pour accéder au cours]({course_url})",
            inline=False
        )
        
        embed.add_field(
            name="📝 Quiz",
            value="Un quiz est disponible à la fin du cours pour tester tes connaissances !",
            inline=False
        )
        
        # Envoyer dans le salon
        await channel.send(embed=embed)
        
        await interaction.followup.send(
            f"✅ Lien du cours **{course_id}** envoyé dans {channel.mention}",
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
