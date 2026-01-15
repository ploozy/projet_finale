"""
Module de gestion de l'onboarding automatique des nouveaux membres
Gère :
- Attribution automatique des rôles
- Création des salons par groupe
- Enregistrement dans la base de données
- Messages de bienvenue
"""

import discord
from discord import PermissionOverwrite
from datetime import datetime, timedelta
from db_connection import SessionLocal
from models import Utilisateur, Cohorte
from cohorte_manager_sql import CohorteManagerSQL
import os


class OnboardingManager:
    """Gère l'arrivée des nouveaux membres et leur attribution à un groupe"""
    
    def __init__(self, bot):
        self.bot = bot
        self.cohort_manager = CohorteManagerSQL()
        
    async def on_member_join(self, member: discord.Member):
        """
        Appelé automatiquement quand un nouveau membre rejoint le serveur
        1. Détermine le groupe (ex: 1-A, 1-B, etc.)
        2. Crée/attribue le rôle
        3. Crée les salons si nécessaire
        4. Enregistre en base
        5. Envoie message de bienvenue
        """
        try:
            guild = member.guild
            
            # 1. Déterminer le groupe disponible
            groupe = await self._get_available_group(guild, niveau=1)
            
            # 2. Créer/Récupérer le rôle
            role = await self._get_or_create_role(guild, groupe)
            
            # 3. Attribuer le rôle
            await member.add_roles(role)
            
            # 4. Créer la catégorie et les salons si nécessaire
            await self._create_group_channels(guild, groupe, role)
            
            # 5. Enregistrer dans PostgreSQL
            cohorte_id = await self._register_user(member.id, member.name, groupe)
            
            # 6. Message de bienvenue
            await self._send_welcome_message(member, groupe, cohorte_id)
            
            print(f"✅ Nouveau membre {member.name} ajouté au {groupe}")
            
        except Exception as e:
            print(f"❌ Erreur onboarding {member.name}: {e}")
            
    async def _get_available_group(self, guild: discord.Guild, niveau: int) -> str:
        """
        Trouve le groupe disponible pour un niveau donné
        Si Groupe X-A a 15+ membres → passe à X-B, etc.
        
        Returns:
            str: "1-A", "1-B", "2-C", etc.
        """
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        
        for letter in letters:
            groupe_name = f"{niveau}-{letter}"
            role = discord.utils.get(guild.roles, name=f"Groupe {groupe_name}")
            
            if role is None:
                # Rôle n'existe pas encore, ce groupe est disponible
                return groupe_name
            
            # Compte combien de membres ont ce rôle
            member_count = len(role.members)
            
            if member_count < 15:
                # Ce groupe a de la place
                return groupe_name
        
        # Si tous les groupes A-J sont pleins (peu probable)
        return f"{niveau}-K"
    
    async def _get_or_create_role(self, guild: discord.Guild, groupe: str) -> discord.Role:
        """
        Récupère ou crée le rôle Discord pour un groupe
        
        Args:
            guild: Le serveur Discord
            groupe: Ex: "1-A", "2-B"
            
        Returns:
            discord.Role: Le rôle créé ou existant
        """
        role_name = f"Groupe {groupe}"
        role = discord.utils.get(guild.roles, name=role_name)
        
        if role is None:
            # Créer le rôle avec une couleur différente par niveau
            colors = {
                1: discord.Color.green(),    # Niveau 1 = Vert
                2: discord.Color.blue(),     # Niveau 2 = Bleu
                3: discord.Color.purple(),   # Niveau 3 = Violet
                4: discord.Color.orange(),   # Niveau 4 = Orange
                5: discord.Color.red()       # Niveau 5 = Rouge
            }
            
            niveau = int(groupe.split('-')[0])
            color = colors.get(niveau, discord.Color.default())
            
            role = await guild.create_role(
                name=role_name,
                color=color,
                mentionable=True,
                reason=f"Création automatique du groupe {groupe}"
            )
            print(f"✅ Rôle '{role_name}' créé")
        
        return role
    
    async def _create_group_channels(self, guild: discord.Guild, groupe: str, role: discord.Role):
        """
        Crée la catégorie et les 3 salons pour un groupe :
        1. #groupe-X-Y-ressources (lecture seule)
        2. #groupe-X-Y-entraide (discussion)
        3. Groupe X-Y Vocal (vocal)
        """
        category_name = f"GROUPE {groupe.upper()}"
        
        # Vérifier si la catégorie existe déjà
        category = discord.utils.get(guild.categories, name=category_name)
        
        if category is None:
            # Créer la catégorie avec permissions
            overwrites = {
                guild.default_role: PermissionOverwrite(read_messages=False),  # Invisible par défaut
                guild.me: PermissionOverwrite(read_messages=True, send_messages=True),  # Bot peut tout faire
                role: PermissionOverwrite(read_messages=True)  # Membres du groupe peuvent voir
            }
            
            category = await guild.create_category(
                name=category_name,
                overwrites=overwrites,
                reason=f"Création automatique de la catégorie {groupe}"
            )
            print(f"✅ Catégorie '{category_name}' créée")
            
            # 1. Salon Ressources (lecture seule pour les membres)
            overwrites_ressources = {
                guild.default_role: PermissionOverwrite(read_messages=False),
                guild.me: PermissionOverwrite(read_messages=True, send_messages=True),
                role: PermissionOverwrite(read_messages=True, send_messages=False)  # Lecture seule
            }
            
            ressources_channel = await category.create_text_channel(
                name=f"groupe-{groupe.lower()}-ressources",
                overwrites=overwrites_ressources,
                topic=f"📚 Ressources et cours pour le Groupe {groupe} | Lecture seule",
                reason=f"Salon ressources du groupe {groupe}"
            )
            
            # Message de bienvenue dans le salon ressources
            await ressources_channel.send(
                f"📚 **Bienvenue dans le salon ressources du Groupe {groupe}** !\n\n"
                f"Ici seront postées toutes les ressources de cours, documents et matériel pédagogique.\n"
                f"Ce salon est en **lecture seule** pour vous permettre de vous concentrer sur le contenu."
            )
            
            # 2. Salon Entraide (discussion libre)
            overwrites_entraide = {
                guild.default_role: PermissionOverwrite(read_messages=False),
                guild.me: PermissionOverwrite(read_messages=True, send_messages=True),
                role: PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    add_reactions=True,
                    embed_links=True,
                    attach_files=True
                )
            }
            
            entraide_channel = await category.create_text_channel(
                name=f"groupe-{groupe.lower()}-entraide",
                overwrites=overwrites_entraide,
                topic=f"💬 Entraide et discussions pour le Groupe {groupe}",
                reason=f"Salon entraide du groupe {groupe}"
            )
            
            await entraide_channel.send(
                f"💬 **Bienvenue dans le salon d'entraide du Groupe {groupe}** !\n\n"
                f"N'hésitez pas à :\n"
                f"• Poser vos questions\n"
                f"• Partager vos solutions\n"
                f"• Aider vos camarades\n"
                f"• Discuter du cours\n\n"
                f"Bon courage à tous ! 🚀"
            )
            
            # 3. Salon Vocal
            overwrites_vocal = {
                guild.default_role: PermissionOverwrite(view_channel=False),
                guild.me: PermissionOverwrite(view_channel=True),
                role: PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True
                )
            }
            
            voice_channel = await category.create_voice_channel(
                name=f"🔊 Groupe {groupe} Vocal",
                overwrites=overwrites_vocal,
                reason=f"Salon vocal du groupe {groupe}"
            )
            
            print(f"✅ Salons créés pour {groupe}")
    
    async def _register_user(self, user_id: int, username: str, groupe: str) -> str:
        """
        Enregistre le nouvel utilisateur dans PostgreSQL
        
        Returns:
            str: ID de la cohorte assignée
        """
        db = SessionLocal()
        try:
            niveau = int(groupe.split('-')[0])
            
            # Utiliser le cohorte_manager pour gérer l'ajout
            cohorte_id = self.cohort_manager.add_user_to_cohort(user_id, username, niveau)
            
            # Mettre à jour le champ groupe
            user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
            if user:
                user.groupe = groupe
                db.commit()
            
            return cohorte_id
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur enregistrement utilisateur: {e}")
            return "UNKNOWN"
        finally:
            db.close()
    
    async def _send_welcome_message(self, member: discord.Member, groupe: str, cohorte_id: str):
        """
        Envoie un message de bienvenue détaillé en MP
        """
        try:
            niveau = int(groupe.split('-')[0])
            
            # URL du site web
            site_url = "https://site-fromation.onrender.com"
            
            # Calculer la date du prochain examen (exemple : dans 14 jours)
            next_exam_date = datetime.now() + timedelta(days=14)
            date_str = next_exam_date.strftime("%d/%m/%Y")
            
            embed = discord.Embed(
                title="🎓 Bienvenue dans la Formation Python !",
                description=f"Bonjour {member.mention}, nous sommes ravis de t'accueillir !",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📌 Ton Groupe",
                value=f"**Groupe {groupe}**\nTu as été assigné à ce groupe automatiquement.",
                inline=False
            )
            
            embed.add_field(
                name="📅 Prochain Examen",
                value=f"Niveau {niveau} - Disponible le **{date_str}**",
                inline=True
            )
            
            embed.add_field(
                name="⏰ Créneau Horaire",
                value="6 heures de disponibilité\n(Durée : 40 minutes)",
                inline=True
            )
            
            embed.add_field(
                name="🌐 Passer ton Examen",
                value=f"Rends-toi sur **[le site web]({site_url}/exams)**\n"
                      f"Entre ton ID Discord : `{member.id}`\n"
                      f"Le système te proposera automatiquement l'examen de ton niveau.",
                inline=False
            )
            
            embed.add_field(
                name="📚 Tes Salons",
                value=f"• `#groupe-{groupe.lower()}-ressources` : Cours et documents\n"
                      f"• `#groupe-{groupe.lower()}-entraide` : Discussions et questions\n"
                      f"• `🔊 Groupe {groupe} Vocal` : Sessions vocales",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Progression",
                value="Réussis ton examen (≥70%) pour passer au niveau suivant !\n"
                      "Si tu échoues, pas de panique, tu peux retenter.",
                inline=False
            )
            
            embed.set_footer(text=f"Cohorte: {cohorte_id} | ID: {member.id}")
            
            await member.send(embed=embed)
            print(f"✅ Message de bienvenue envoyé à {member.name}")
            
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name} (MPs désactivés)")
        except Exception as e:
            print(f"❌ Erreur envoi message bienvenue: {e}")
