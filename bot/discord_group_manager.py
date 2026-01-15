"""
Gestionnaire des groupes Discord (rôles et salons)
Gère la création automatique et l'attribution des groupes A, B, C, etc.
"""
import discord
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime
from models import DiscordGroup, Utilisateur
from db_connection import SessionLocal

class DiscordGroupManager:
    """Gère les rôles et salons Discord pour chaque niveau"""
    
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.max_membres_par_groupe = 15
        
    async def get_or_create_group(self, niveau: int, user_id: int) -> tuple:
        """
        Trouve ou crée un groupe Discord pour un utilisateur
        Returns: (role_id, channel_id, sous_groupe)
        """
        db = SessionLocal()
        try:
            # Chercher un groupe existant avec de la place
            groups = db.query(DiscordGroup).filter(
                DiscordGroup.niveau == niveau
            ).order_by(DiscordGroup.sous_groupe).all()
            
            for group in groups:
                # Compter les membres actuels
                membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                    and_(
                        Utilisateur.niveau_actuel == niveau,
                        Utilisateur.sous_groupe == group.sous_groupe
                    )
                ).scalar()
                
                if membres_count < self.max_membres_par_groupe:
                    return (group.role_id, group.channel_id, group.sous_groupe)
            
            # Aucun groupe avec de la place, créer un nouveau
            next_sous_groupe = self._get_next_sous_groupe(groups)
            role, channel = await self._create_discord_group(niveau, next_sous_groupe)
            
            # Enregistrer dans la base de données
            new_group = DiscordGroup(
                niveau=niveau,
                sous_groupe=next_sous_groupe,
                role_id=role.id,
                channel_id=channel.id,
                max_membres=self.max_membres_par_groupe,
                date_creation=datetime.now()
            )
            db.add(new_group)
            db.commit()
            
            print(f"✅ Nouveau groupe créé : Groupe-{niveau}{next_sous_groupe}")
            return (role.id, channel.id, next_sous_groupe)
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur get_or_create_group: {e}")
            raise
        finally:
            db.close()
    
    def _get_next_sous_groupe(self, existing_groups: list) -> str:
        """Détermine la prochaine lettre disponible (A, B, C, ...)"""
        if not existing_groups:
            return 'A'
        
        used_letters = [g.sous_groupe for g in existing_groups]
        letter = 'A'
        while letter in used_letters:
            letter = chr(ord(letter) + 1)
        return letter
    
    async def _create_discord_group(self, niveau: int, sous_groupe: str) -> tuple:
        """
        Crée un rôle et un salon Discord pour un groupe
        Returns: (role, channel)
        """
        try:
            # Créer le rôle
            role_name = f"Groupe-{niveau}{sous_groupe}"
            role = await self.guild.create_role(
                name=role_name,
                color=discord.Color.blue(),
                mentionable=True,
                reason=f"Création automatique groupe niveau {niveau}"
            )
            
            # Trouver ou créer la catégorie
            category = await self._get_or_create_category(niveau)
            
            # Créer le salon privé
            channel_name = f"groupe-{niveau}{sous_groupe}"
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                self.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            channel = await self.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Salon privé pour le {role_name}"
            )
            
            # Message de bienvenue
            embed = discord.Embed(
                title=f"🎓 Bienvenue dans le {role_name}",
                description=f"Ce salon est réservé aux membres du groupe {niveau}{sous_groupe}.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📚 Objectif",
                value=f"Réussir l'examen de niveau {niveau} pour passer au niveau suivant",
                inline=False
            )
            embed.add_field(
                name="👥 Capacité",
                value=f"Maximum {self.max_membres_par_groupe} membres",
                inline=True
            )
            await channel.send(embed=embed)
            
            print(f"✅ Rôle et salon créés : {role_name}")
            return (role, channel)
            
        except Exception as e:
            print(f"❌ Erreur _create_discord_group: {e}")
            raise
    
    async def _get_or_create_category(self, niveau: int) -> discord.CategoryChannel:
        """Trouve ou crée une catégorie pour un niveau"""
        category_name = f"📚 NIVEAU {niveau}"
        
        # Chercher la catégorie existante
        for category in self.guild.categories:
            if category.name == category_name:
                return category
        
        # Créer la catégorie
        category = await self.guild.create_category(
            name=category_name,
            reason=f"Catégorie pour niveau {niveau}"
        )
        return category
    
    async def assign_user_to_group(self, member: discord.Member, niveau: int, sous_groupe: str, role_id: int):
        """Assigne un utilisateur à son groupe Discord"""
        try:
            # Récupérer le rôle
            role = self.guild.get_role(role_id)
            if not role:
                print(f"⚠️ Rôle {role_id} introuvable")
                return False
            
            # Retirer les anciens rôles de groupe
            old_roles = [r for r in member.roles if r.name.startswith("Groupe-")]
            if old_roles:
                await member.remove_roles(*old_roles, reason="Changement de groupe")
            
            # Assigner le nouveau rôle
            await member.add_roles(role, reason=f"Assignation au groupe {niveau}{sous_groupe}")
            print(f"✅ {member.name} assigné au Groupe-{niveau}{sous_groupe}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur assign_user_to_group: {e}")
            return False
    
    async def remove_user_from_group(self, member: discord.Member):
        """Retire tous les rôles de groupe d'un utilisateur"""
        try:
            group_roles = [r for r in member.roles if r.name.startswith("Groupe-")]
            if group_roles:
                await member.remove_roles(*group_roles, reason="Retrait du groupe")
                print(f"✅ {member.name} retiré de ses groupes")
        except Exception as e:
            print(f"❌ Erreur remove_user_from_group: {e}")
    
    def get_group_info(self, niveau: int, sous_groupe: str) -> dict:
        """Récupère les informations d'un groupe"""
        db = SessionLocal()
        try:
            group = db.query(DiscordGroup).filter(
                and_(
                    DiscordGroup.niveau == niveau,
                    DiscordGroup.sous_groupe == sous_groupe
                )
            ).first()
            
            if not group:
                return None
            
            # Compter les membres
            membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                and_(
                    Utilisateur.niveau_actuel == niveau,
                    Utilisateur.sous_groupe == sous_groupe
                )
            ).scalar()
            
            return {
                'niveau': group.niveau,
                'sous_groupe': group.sous_groupe,
                'role_id': group.role_id,
                'channel_id': group.channel_id,
                'membres_count': membres_count,
                'max_membres': group.max_membres,
                'date_creation': group.date_creation.isoformat()
            }
        finally:
            db.close()
    
    def get_all_groups(self) -> list:
        """Récupère tous les groupes Discord"""
        db = SessionLocal()
        try:
            groups = db.query(DiscordGroup).order_by(
                DiscordGroup.niveau, DiscordGroup.sous_groupe
            ).all()
            
            result = []
            for group in groups:
                membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                    and_(
                        Utilisateur.niveau_actuel == group.niveau,
                        Utilisateur.sous_groupe == group.sous_groupe
                    )
                ).scalar()
                
                result.append({
                    'niveau': group.niveau,
                    'sous_groupe': group.sous_groupe,
                    'role_id': group.role_id,
                    'channel_id': group.channel_id,
                    'membres_count': membres_count,
                    'max_membres': group.max_membres
                })
            
            return result
        finally:
            db.close()
