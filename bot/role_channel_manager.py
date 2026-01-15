"""
Gestionnaire automatique de rôles et salons Discord
S'exécute en arrière-plan pour synchroniser les utilisateurs
"""
import discord
from discord.ext import tasks
from cohorte_manager_sql import CohortManagerSQL
from role_channel_manager import RoleChannelManager
from db_connection import SessionLocal
from models import Utilisateur
import asyncio


class AutoRoleManager:
    """Synchronise automatiquement les rôles Discord avec la base de données"""
    
    def __init__(self, bot):
        self.bot = bot
        self.cohort_manager = CohortManagerSQL()
        self.role_manager = RoleChannelManager(bot)
        
    def start(self):
        """Démarre la synchronisation automatique"""
        if not self.auto_sync_roles.is_running():
            self.auto_sync_roles.start()
            print("✅ Synchronisation automatique des rôles démarrée")
    
    def stop(self):
        """Arrête la synchronisation"""
        if self.auto_sync_roles.is_running():
            self.auto_sync_roles.cancel()
    
    @tasks.loop(minutes=5)  # Vérifie toutes les 5 minutes
    async def auto_sync_roles(self):
        """Synchronise automatiquement tous les utilisateurs avec leurs rôles"""
        try:
            print("🔄 Synchronisation automatique des rôles...")
            
            db = SessionLocal()
            users = db.query(Utilisateur).all()
            db.close()
            
            synced = 0
            for user_data in users:
                try:
                    user_id = user_data.user_id
                    cohorte_id = user_data.cohorte_id
                    niveau = user_data.niveau_actuel
                    
                    # Parcourir tous les serveurs
                    for guild in self.bot.guilds:
                        member = guild.get_member(user_id)
                        
                        if member:
                            # Vérifier si le membre a le bon rôle
                            await self._ensure_member_has_correct_role(
                                guild, member, cohorte_id, niveau
                            )
                            synced += 1
                
                except Exception as e:
                    print(f"⚠️ Erreur sync pour {user_data.username}: {e}")
                    continue
            
            if synced > 0:
                print(f"✅ {synced} utilisateur(s) synchronisé(s)")
        
        except Exception as e:
            print(f"❌ Erreur auto_sync_roles: {e}")
    
    async def _ensure_member_has_correct_role(self, guild, member, cohorte_id, niveau):
        """Assure qu'un membre a le bon rôle pour sa cohorte"""
        try:
            # Récupérer les infos de la cohorte
            cohort_info = self.cohort_manager.get_cohort_info(cohorte_id)
            
            if not cohort_info:
                return
            
            # Créer/récupérer le rôle et salon si nécessaire
            role, channel = await self.role_manager.ensure_cohort_resources(
                guild, cohorte_id, niveau
            )
            
            if not role:
                return
            
            # Vérifier si le membre a ce rôle
            if role not in member.roles:
                # Retirer tous les anciens rôles de groupe
                for old_role in member.roles:
                    if old_role.name.startswith("Groupe-"):
                        await member.remove_roles(old_role)
                
                # Ajouter le bon rôle
                await member.add_roles(role)
                print(f"✅ Rôle {role.name} attribué à {member.name}")
        
        except Exception as e:
            print(f"⚠️ Erreur _ensure_member_has_correct_role: {e}")
    
    async def process_new_user(self, guild, user_id, username):
        """
        Traite un nouvel utilisateur : inscription BDD + rôle Discord
        Appelé depuis app.py après inscription automatique
        """
        try:
            # Récupérer les infos de l'utilisateur
            user_info = self.cohort_manager.get_user_info(user_id)
            
            if not user_info:
                print(f"⚠️ Utilisateur {user_id} non trouvé en BDD")
                return
            
            cohorte_id = user_info['cohorte_id']
            niveau = user_info['niveau_actuel']
            
            # Créer le rôle et salon
            role, channel = await self.role_manager.ensure_cohort_resources(
                guild, cohorte_id, niveau
            )
            
            # Récupérer le membre Discord
            member = guild.get_member(user_id)
            
            if member and role:
                await member.add_roles(role)
                print(f"✅ Rôle automatique attribué à {username}")
                
                # Message de bienvenue dans le salon
                if channel:
                    embed = discord.Embed(
                        title="🎉 Nouveau membre !",
                        description=f"{member.mention} vient de rejoindre le groupe **{cohorte_id}**",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📊 Niveau",
                        value=f"Niveau {niveau}",
                        inline=True
                    )
                    await channel.send(embed=embed)
        
        except Exception as e:
            print(f"❌ Erreur process_new_user: {e}")
            import traceback
            traceback.print_exc()
    
    @auto_sync_roles.before_loop
    async def before_auto_sync(self):
        """Attend que le bot soit prêt avant de démarrer"""
        await self.bot.wait_until_ready()
        print("⏰ Auto-synchronisation des rôles prête")
