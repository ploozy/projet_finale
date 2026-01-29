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
from group_manager import GroupManager
from cohort_config import TEMPS_FORMATION_MINIMUM
import os


class OnboardingManager:
    """Gère l'arrivée des nouveaux membres et leur attribution à un groupe"""

    def __init__(self, bot):
        self.bot = bot
        # Utiliser le nouveau GroupManager au lieu de CohorteManagerSQL
        self.pending_confirmations = {}  # user_id -> {groupe, niveau, temps_restant}
        
    async def on_member_join(self, member: discord.Member):
        """
        Appelé automatiquement quand un nouveau membre rejoint le serveur
        Utilise le nouveau GroupManager pour gérer l'inscription
        """
        try:
            guild = member.guild
            db = SessionLocal()
            group_manager = GroupManager(db)

            # Tenter l'inscription
            groupe, info = group_manager.register_user(member.id, member.name, niveau=1)

            if info['status'] == 'direct':
                # Inscription directe réussie
                await self._complete_onboarding(member, groupe, guild)
                print(f"✅ Nouveau membre {member.name} ajouté au {groupe}")

            elif info['status'] == 'needs_confirmation':
                # Temps insuffisant, demander confirmation
                self.pending_confirmations[member.id] = {
                    'groupe': info['groupe'],
                    'niveau': 1,
                    'temps_restant_jours': info['temps_restant_jours'],
                    'temps_minimum': info['temps_formation_minimum']
                }
                await self._ask_confirmation(member, info)
                print(f"⚠️ {member.name} : confirmation nécessaire (temps insuffisant)")

            elif info['status'] == 'waiting_list':
                # Ajouté à la waiting list
                await self._send_waiting_list_message(member, info)
                print(f"📋 {member.name} ajouté à la waiting list ({info['waiting_list_type']})")

            elif info['status'] == 'already_registered':
                # Déjà enregistré
                await member.send("Tu es déjà enregistré dans le système !")
                print(f"ℹ️ {member.name} : déjà enregistré")

            db.close()

        except Exception as e:
            print(f"❌ Erreur onboarding {member.name}: {e}")
            import traceback
            traceback.print_exc()

    async def _complete_onboarding(self, member: discord.Member, groupe: str, guild: discord.Guild):
        """Complete l'onboarding après confirmation ou inscription directe"""
        # Créer/Récupérer le rôle
        role = await self._get_or_create_role(guild, groupe)

        # Attribuer le rôle
        await member.add_roles(role)

        # Créer la catégorie et les salons si nécessaire
        await self._create_group_channels(guild, groupe, role)

        # Message de bienvenue
        await self._send_welcome_message(member, groupe)

    async def _ask_confirmation(self, member: discord.Member, info: dict):
        """Demande confirmation à l'utilisateur quand le temps est insuffisant"""
        temps_restant = info['temps_restant_jours']
        temps_minimum = info['temps_formation_minimum']
        groupe = info['groupe']

        # Convertir en heures et minutes
        heures = int(temps_restant * 24)
        minutes = int((temps_restant * 24 - heures) * 60)

        embed = discord.Embed(
            title="⚠️ Attention : Temps de Formation Insuffisant",
            description=f"Le groupe {groupe} a un examen programmé dans peu de temps.",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="⏰ Temps Restant",
            value=f"**{heures}h {minutes}min** avant l'examen",
            inline=True
        )

        embed.add_field(
            name="📚 Temps Recommandé",
            value=f"**{int(temps_minimum * 24)}h** (minimum)",
            inline=True
        )

        embed.add_field(
            name="💡 Que faire ?",
            value="Tu peux :\n"
                  "• ✅ **Rejoindre quand même** : Réagis avec ✅\n"
                  "• ❌ **Attendre un autre groupe** : Réagis avec ❌\n\n"
                  "Tu as 5 minutes pour décider.",
            inline=False
        )

        msg = await member.send(embed=embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')

    async def handle_confirmation_reaction(self, user_id: int, accepted: bool, guild: discord.Guild):
        """Gère la réponse de confirmation de l'utilisateur"""
        if user_id not in self.pending_confirmations:
            return

        info = self.pending_confirmations.pop(user_id)
        membre = guild.get_member(user_id)

        if not membre:
            return

        db = SessionLocal()
        group_manager = GroupManager(db)

        if accepted:
            # Confirmer l'inscription
            groupe = group_manager.confirm_registration_with_insufficient_time(
                user_id,
                membre.name,
                info['niveau'],
                info['groupe']
            )
            await self._complete_onboarding(membre, groupe, guild)
            await membre.send(f"✅ Inscription confirmée dans le groupe {groupe} !")
            print(f"✅ {membre.name} a accepté de rejoindre {groupe} malgré le temps insuffisant")

        else:
            # Chercher un autre groupe ou waiting list
            groupe, new_info = group_manager.register_user(user_id, membre.name, niveau=info['niveau'])

            if new_info['status'] == 'direct':
                await self._complete_onboarding(membre, groupe, guild)
                await membre.send(f"✅ Tu as été assigné au groupe {groupe} avec plus de temps de préparation !")

            elif new_info['status'] == 'waiting_list':
                await self._send_waiting_list_message(membre, new_info)

        db.close()

    async def _send_waiting_list_message(self, member: discord.Member, info: dict):
        """Envoie un message à un utilisateur en waiting list"""
        embed = discord.Embed(
            title="📋 Waiting List",
            description="Tu as été ajouté à la liste d'attente.",
            color=discord.Color.blue()
        )

        if info['waiting_list_type'] == 'nouveau_groupe':
            embed.add_field(
                name="📊 Situation",
                value=f"Les groupes existants sont pleins ou n'ont pas assez de temps.\n"
                      f"Dès que **7 personnes** seront en attente, un nouveau groupe sera créé automatiquement !",
                inline=False
            )
        else:
            embed.add_field(
                name="📊 Situation",
                value="Tous les groupes (A-Z) sont pleins.\n"
                      "Tu seras assigné dès qu'une place se libère.",
                inline=False
            )

        embed.add_field(
            name="💡 Que faire ?",
            value="Tu recevras un MP automatiquement quand ton groupe sera prêt !",
            inline=False
        )

        await member.send(embed=embed)
            
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
                hoist=True,  # Afficher séparément à gauche sur Discord
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
    
    async def _send_welcome_message(self, member: discord.Member, groupe: str):
        """
        Envoie un message de bienvenue détaillé en MP
        """
        try:
            niveau = int(groupe.split('-')[0])
            
            # URL du site web
            site_url = "http://localhost:5000"
            
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
            
            embed.set_footer(text=f"Groupe: {groupe} | ID: {member.id}")
            
            await member.send(embed=embed)
            print(f"✅ Message de bienvenue envoyé à {member.name}")
            
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name} (MPs désactivés)")
        except Exception as e:
            print(f"❌ Erreur envoi message bienvenue: {e}")
