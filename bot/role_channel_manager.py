"""
Gestionnaire de rôles et salons Discord pour les cohortes
Crée automatiquement les rôles et salons privés par groupe
"""
import discord
from cohorte_manager_sql import CohortManagerSQL
from db_connection import SessionLocal
from models import Cohorte
from sqlalchemy import func


class RoleChannelManager:
    """Gère la création et l'attribution des rôles et salons Discord"""
    
    def __init__(self, bot):
        self.bot = bot
        self.cohort_manager = CohortManagerSQL()
    
    async def ensure_cohort_resources(self, guild: discord.Guild, cohorte_id: str, niveau: int):
        """
        Crée ou récupère le rôle et le salon pour une cohorte
        
        Args:
            guild: Le serveur Discord
            cohorte_id: ID de la cohorte (ex: JAN26-A)
            niveau: Niveau de la cohorte (1-5)
            
        Returns:
            tuple: (role, channel)
        """
        db = SessionLocal()
        try:
            cohort = db.query(Cohorte).filter(Cohorte.id == cohorte_id).first()
            
            if not cohort:
                print(f"❌ Cohorte {cohorte_id} introuvable")
                return None, None
            
            # Vérifier si le rôle existe déjà
            if cohort.role_id:
                role = guild.get_role(cohort.role_id)
                if not role:
                    # Le rôle a été supprimé, en créer un nouveau
                    role = await self._create_role(guild, cohorte_id, niveau)
                    cohort.role_id = role.id
            else:
                # Créer le rôle
                role = await self._create_role(guild, cohorte_id, niveau)
                cohort.role_id = role.id
            
            # Vérifier si le salon existe déjà
            if cohort.channel_id:
                channel = guild.get_channel(cohort.channel_id)
                if not channel:
                    # Le salon a été supprimé, en créer un nouveau
                    channel = await self._create_channel(guild, cohorte_id, niveau, role)
                    cohort.channel_id = channel.id
            else:
                # Créer le salon
                channel = await self._create_channel(guild, cohorte_id, niveau, role)
                cohort.channel_id = channel.id
            
            # Sauvegarder dans la base
            cohort.guild_id = guild.id
            db.commit()
            
            return role, channel
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur ensure_cohort_resources: {e}")
            import traceback
            traceback.print_exc()
            return None, None
        finally:
            db.close()
    
    async def _create_role(self, guild: discord.Guild, cohorte_id: str, niveau: int):
        """Crée un rôle Discord pour une cohorte"""
        
        # Couleurs par niveau
        colors = {
            1: discord.Color.green(),
            2: discord.Color.blue(),
            3: discord.Color.purple(),
            4: discord.Color.orange(),
            5: discord.Color.red()
        }
        
        role = await guild.create_role(
            name=f"Groupe-{niveau}-{cohorte_id}",
            color=colors.get(niveau, discord.Color.default()),
            mentionable=True,
            reason=f"Cohorte {cohorte_id} - Niveau {niveau}"
        )
        
        print(f"✅ Rôle créé: {role.name}")
        return role
    
    async def _create_channel(self, guild: discord.Guild, cohorte_id: str, niveau: int, role: discord.Role):
        """Crée un salon privé Discord pour une cohorte"""
        
        # Trouver ou créer la catégorie "Groupes de Formation"
        category = discord.utils.get(guild.categories, name="Groupes de Formation")
        if not category:
            category = await guild.create_category("Groupes de Formation")
        
        # Permissions du salon
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await guild.create_text_channel(
            name=f"groupe-{niveau}-{cohorte_id.lower()}",
            category=category,
            overwrites=overwrites,
            topic=f"Salon privé pour la cohorte {cohorte_id} - Niveau {niveau}"
        )
        
        # Message de bienvenue
        embed = discord.Embed(
            title=f"🎓 Bienvenue dans le groupe {cohorte_id}",
            description=f"Vous êtes actuellement au **Niveau {niveau}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📚 Objectif",
            value="Progresser ensemble vers le prochain niveau",
            inline=False
        )
        embed.add_field(
            name="📅 Calendrier",
            value="Consultez vos prochains examens avec `/my_group`",
            inline=False
        )
        
        await channel.send(embed=embed)
        
        print(f"✅ Salon créé: {channel.name}")
        return channel
    
    async def update_member_role(self, guild: discord.Guild, member: discord.Member, new_niveau: int):
        """
        Met à jour le rôle d'un membre après passage de niveau
        
        Args:
            guild: Le serveur Discord
            member: Le membre Discord
            new_niveau: Le nouveau niveau du membre
        """
        try:
            # Récupérer les infos du membre
            user_info = self.cohort_manager.get_user_info(member.id)
            if not user_info:
                return
            
            cohorte_id = user_info['cohorte_id']
            cohort_info = self.cohort_manager.get_cohort_info(cohorte_id)
            
            # Retirer tous les anciens rôles de groupe
            for role in member.roles:
                if role.name.startswith("Groupe-"):
                    await member.remove_roles(role)
                    print(f"🔽 Rôle retiré: {role.name} de {member.name}")
            
            # Créer/récupérer le nouveau rôle et salon
            role, channel = await self.ensure_cohort_resources(guild, cohorte_id, new_niveau)
            
            if role:
                await member.add_roles(role)
                print(f"🔼 Nouveau rôle attribué: {role.name} à {member.name}")
            
            # Envoyer un message dans le nouveau salon
            if channel:
                embed = discord.Embed(
                    title="🎉 Nouveau membre !",
                    description=f"{member.mention} vient de rejoindre le groupe",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)
        
        except Exception as e:
            print(f"❌ Erreur update_member_role: {e}")
            import traceback
            traceback.print_exc()
    
    async def sync_existing_cohorts(self, guild: discord.Guild):
        """
        Synchronise les rôles et salons existants avec la base de données
        À exécuter au démarrage du bot
        """
        db = SessionLocal()
        try:
            cohorts = db.query(Cohorte).all()
            
            for cohort in cohorts:
                # Créer/récupérer les ressources Discord
                role, channel = await self.ensure_cohort_resources(
                    guild, 
                    cohort.id, 
                    cohort.niveau_actuel
                )
                
                # Attribuer les rôles aux membres existants
                members_info = self.cohort_manager.get_cohort_members(cohort.id)
                
                for member_info in members_info:
                    member = guild.get_member(member_info['user_id'])
                    if member and role:
                        # Vérifier si le membre a déjà le rôle
                        if role not in member.roles:
                            await member.add_roles(role)
                            print(f"✅ Rôle {role.name} attribué à {member.name}")
            
            print(f"✅ Synchronisation de {len(cohorts)} cohortes terminée")
        
        except Exception as e:
            print(f"❌ Erreur sync_existing_cohorts: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    async def handle_cohort_full(self, guild: discord.Guild, niveau: int):
        """
        Crée une nouvelle cohorte quand une cohorte est pleine (20 membres)
        
        Args:
            guild: Le serveur Discord
            niveau: Le niveau de la nouvelle cohorte
            
        Returns:
            str: ID de la nouvelle cohorte créée
        """
        # Créer une nouvelle cohorte
        from datetime import datetime, timedelta
        
        # Premier examen dans 14 jours
        first_exam_date = datetime.now() + timedelta(days=14)
        
        new_cohort_id = self.cohort_manager.create_cohort(first_exam_date)
        
        # Créer les ressources Discord
        role, channel = await self.ensure_cohort_resources(guild, new_cohort_id, niveau)
        
        print(f"✅ Nouvelle cohorte créée: {new_cohort_id}")
        return new_cohort_id
