"""
Module de gestion de la promotion automatique des utilisateurs
Gère :
- Lecture des résultats d'examens web
- Promotion au niveau supérieur si réussite
- Changement de rôles Discord
- Accès aux nouveaux salons
- Notifications
"""

import discord
from discord import PermissionOverwrite
from datetime import datetime
from db_connection import SessionLocal
from models import Utilisateur, ExamResult
from onboarding import OnboardingManager


class PromotionManager:
    """Gère la promotion des utilisateurs suite aux résultats d'examens"""
    
    def __init__(self, bot):
        self.bot = bot
        self.onboarding = OnboardingManager(bot)
    
    async def check_and_notify_results(self, guild: discord.Guild):
        """
        Vérifie les résultats d'examens non notifiés
        et effectue les promotions/notifications nécessaires
        
        Appelé par la commande /check_exam_results (admin)
        """
        db = SessionLocal()
        try:
            # Récupérer tous les résultats non notifiés
            results = db.query(ExamResult).filter(
                ExamResult.notified == False
            ).all()
            
            if not results:
                return "✅ Aucun nouveau résultat à notifier."
            
            notifications_sent = 0
            promotions_done = 0
            
            for result in results:
                try:
                    # Récupérer l'utilisateur Discord
                    member = guild.get_member(result.user_id)
                    
                    if member is None:
                        # Utilisateur n'est plus sur le serveur
                        result.notified = True
                        continue
                    
                    # Récupérer les infos utilisateur de la DB
                    user_db = db.query(Utilisateur).filter(
                        Utilisateur.user_id == result.user_id
                    ).first()
                    
                    if user_db is None:
                        result.notified = True
                        continue
                    
                    if result.passed:
                        # ✅ RÉUSSITE - Promotion
                        await self._promote_user(member, user_db, result, db, guild)
                        promotions_done += 1
                    else:
                        # ❌ ÉCHEC - Reste dans le même groupe
                        await self._notify_failure(member, user_db, result)
                    
                    # Marquer comme notifié
                    result.notified = True
                    notifications_sent += 1
                    
                except Exception as e:
                    print(f"❌ Erreur traitement résultat {result.id}: {e}")
                    continue
            
            db.commit()
            
            return (f"✅ **Résultats traités**\n"
                   f"📧 Notifications envoyées : {notifications_sent}\n"
                   f"🎉 Promotions effectuées : {promotions_done}")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur check_and_notify_results: {e}")
            return f"❌ Erreur lors de la vérification : {e}"
        finally:
            db.close()
    
    async def _promote_user(
        self, 
        member: discord.Member, 
        user_db: Utilisateur, 
        result: ExamResult,
        db,
        guild: discord.Guild
    ):
        """
        Promeut un utilisateur au niveau supérieur
        1. Change niveau_actuel en DB
        2. Retire ancien rôle Discord
        3. Attribue nouveau rôle
        4. Crée salons si nécessaire
        5. Envoie notification de félicitations
        """
        try:
            # 1. Calculer le nouveau niveau
            old_niveau = user_db.niveau_actuel
            new_niveau = old_niveau + 1
            old_groupe = user_db.groupe
            
            # Trouver un groupe disponible au nouveau niveau
            new_groupe = await self.onboarding._get_available_group(guild, new_niveau)
            
            # 2. Mettre à jour la base de données
            user_db.niveau_actuel = new_niveau
            user_db.groupe = new_groupe
            user_db.examens_reussis += 1
            db.commit()
            
            # 3. Retirer l'ancien rôle Discord
            old_role = discord.utils.get(guild.roles, name=f"Groupe {old_groupe}")
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
                print(f"✅ Rôle {old_role.name} retiré de {member.name}")
            
            # 4. Créer/Récupérer le nouveau rôle
            new_role = await self.onboarding._get_or_create_role(guild, new_groupe)
            await member.add_roles(new_role)
            print(f"✅ Rôle {new_role.name} attribué à {member.name}")
            
            # 5. Créer les salons si nécessaire
            await self.onboarding._create_group_channels(guild, new_groupe, new_role)
            
            # 6. Envoyer notification de félicitations
            await self._send_promotion_message(member, old_groupe, new_groupe, result)
            
            print(f"🎉 {member.name} promu de {old_groupe} à {new_groupe}")
            
        except Exception as e:
            print(f"❌ Erreur promotion utilisateur {member.name}: {e}")
            db.rollback()
            raise
    
    async def _send_promotion_message(
        self,
        member: discord.Member,
        old_groupe: str,
        new_groupe: str,
        result: ExamResult
    ):
        """
        Envoie un message de félicitations pour la promotion
        """
        try:
            embed = discord.Embed(
                title="🎉 Félicitations ! Tu as réussi !",
                description=f"{member.mention}, tu as brillamment réussi ton examen !",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Résultat",
                value=f"**{result.percentage:.1f}%** ({result.score}/{result.total})\n"
                      f"Seuil requis : {result.passing_score}%",
                inline=False
            )
            
            embed.add_field(
                name="🆙 Progression",
                value=f"**{old_groupe}** → **{new_groupe}**",
                inline=True
            )
            
            new_niveau = int(new_groupe.split('-')[0])
            embed.add_field(
                name="📚 Nouveau Niveau",
                value=f"**Niveau {new_niveau}**",
                inline=True
            )
            
            embed.add_field(
                name="🔓 Nouveaux Salons Débloqués",
                value=f"• `#groupe-{new_groupe.lower()}-ressources`\n"
                      f"• `#groupe-{new_groupe.lower()}-entraide`\n"
                      f"• `🔊 Groupe {new_groupe} Vocal`",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Accès aux Anciens Salons",
                value=f"Tu n'as plus accès aux salons du **Groupe {old_groupe}**.\n"
                      f"Concentre-toi maintenant sur ton nouveau niveau !",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Prochaine Étape",
                value="Continue ton apprentissage et prépare-toi pour le prochain examen !\n"
                      "Bon courage ! 💪",
                inline=False
            )
            
            embed.set_footer(text=f"Examen passé le {result.date.strftime('%d/%m/%Y à %H:%M')}")
            
            await member.send(embed=embed)
            print(f"✅ Message de promotion envoyé à {member.name}")
            
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name} (MPs désactivés)")
        except Exception as e:
            print(f"❌ Erreur envoi message promotion: {e}")
    
    async def _notify_failure(
        self,
        member: discord.Member,
        user_db: Utilisateur,
        result: ExamResult
    ):
        """
        Notifie l'utilisateur qu'il n'a pas réussi l'examen
        Il reste dans son groupe actuel
        """
        try:
            embed = discord.Embed(
                title="📚 Résultat de ton Examen",
                description=f"{member.mention}, voici le résultat de ton dernier examen.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Score Obtenu",
                value=f"**{result.percentage:.1f}%** ({result.score}/{result.total})",
                inline=True
            )
            
            embed.add_field(
                name="🎯 Score Requis",
                value=f"**{result.passing_score}%**",
                inline=True
            )
            
            points_needed = result.passing_score - result.percentage
            embed.add_field(
                name="📈 Progression",
                value=f"Il te manque **{points_needed:.1f}%** pour réussir.",
                inline=False
            )
            
            embed.add_field(
                name="🔄 Prochaines Étapes",
                value=f"• Tu restes dans le **Groupe {user_db.groupe}**\n"
                      f"• Révise les points difficiles\n"
                      f"• Consulte les ressources dans ton salon\n"
                      f"• Demande de l'aide dans `#groupe-{user_db.groupe.lower()}-entraide`\n"
                      f"• Tu pourras retenter l'examen bientôt !",
                inline=False
            )
            
            embed.add_field(
                name="💪 Motivation",
                value="Ne te décourage pas ! L'échec fait partie de l'apprentissage.\n"
                      "Continue à t'entraîner, tu vas y arriver ! 🚀",
                inline=False
            )
            
            embed.set_footer(text=f"Examen passé le {result.date.strftime('%d/%m/%Y à %H:%M')}")
            
            await member.send(embed=embed)
            print(f"✅ Notification d'échec envoyée à {member.name}")
            
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP à {member.name} (MPs désactivés)")
        except Exception as e:
            print(f"❌ Erreur envoi notification échec: {e}")
