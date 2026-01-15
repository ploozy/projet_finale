"""
Système de Vote pour Récompense d'Entraide
Permet aux membres d'un groupe de voter pour 3 personnes maximum
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from db_connection import SessionLocal
from models import Utilisateur, Vote, ExamPeriod
from sqlalchemy import func


class VoteSystem:
    """Gestion du système de vote"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_active_exam_period(self, group_number: int) -> ExamPeriod:
        """Récupère la période d'examen active pour un groupe"""
        db = SessionLocal()
        try:
            now = datetime.now()
            period = db.query(ExamPeriod).filter(
                ExamPeriod.group_number == group_number,
                ExamPeriod.start_time <= now,
                ExamPeriod.end_time >= now,
                ExamPeriod.votes_closed == False
            ).first()
            
            return period
        finally:
            db.close()
    
    async def vote_command(
        self, 
        interaction: discord.Interaction, 
        user1: discord.Member = None,
        user2: discord.Member = None,
        user3: discord.Member = None
    ):
        """
        Commande /vote pour voter pour 1 à 3 personnes
        """
        await interaction.response.defer(ephemeral=True)
        
        db = SessionLocal()
        try:
            voter_id = interaction.user.id
            
            # 1. Vérifier que l'utilisateur existe dans la DB
            voter = db.query(Utilisateur).filter(
                Utilisateur.user_id == voter_id
            ).first()
            
            if not voter:
                await interaction.followup.send(
                    "❌ Tu dois d'abord t'inscrire avec `/register`",
                    ephemeral=True
                )
                return
            
            # 2. Vérifier qu'il y a une période d'examen active
            exam_period = self.get_active_exam_period(voter.niveau_actuel)
            
            if not exam_period:
                await interaction.followup.send(
                    "❌ Aucune période d'examen active pour ton groupe.\n"
                    "Les votes sont ouverts pendant les 6h d'examen.",
                    ephemeral=True
                )
                return
            
            # 3. Vérifier que l'utilisateur n'a pas déjà voté
            existing_votes = db.query(Vote).filter(
                Vote.voter_id == voter_id,
                Vote.exam_period_id == exam_period.id
            ).count()
            
            if existing_votes > 0:
                await interaction.followup.send(
                    f"❌ Tu as déjà voté pour cette période d'examen !\n"
                    f"Tu as voté pour {existing_votes} personne(s).\n\n"
                    f"Si tu veux modifier tes votes, contacte un administrateur.",
                    ephemeral=True
                )
                return
            
            # 4. Collecter les votes
            voted_users = []
            for user in [user1, user2, user3]:
                if user is not None:
                    voted_users.append(user)
            
            if len(voted_users) == 0:
                await interaction.followup.send(
                    "❌ Tu dois voter pour au moins 1 personne !",
                    ephemeral=True
                )
                return
            
            # 5. Vérifier qu'on ne vote pas pour soi-même
            for user in voted_users:
                if user.id == voter_id:
                    await interaction.followup.send(
                        "❌ Tu ne peux pas voter pour toi-même !",
                        ephemeral=True
                    )
                    return
            
            # 6. Vérifier que toutes les personnes sont du même groupe
            errors = []
            for user in voted_users:
                user_db = db.query(Utilisateur).filter(
                    Utilisateur.user_id == user.id
                ).first()
                
                if not user_db:
                    errors.append(f"❌ {user.mention} n'est pas inscrit dans le système")
                elif user_db.niveau_actuel != voter.niveau_actuel:
                    errors.append(
                        f"❌ {user.mention} n'est pas dans ton groupe (Niveau {user_db.niveau_actuel} vs {voter.niveau_actuel})"
                    )
            
            if errors:
                await interaction.followup.send(
                    "❌ **Erreurs détectées :**\n\n" + "\n".join(errors),
                    ephemeral=True
                )
                return
            
            # 7. Enregistrer les votes
            for user in voted_users:
                vote = Vote(
                    voter_id=voter_id,
                    voted_for_id=user.id,
                    exam_period_id=exam_period.id,
                    date=datetime.now()
                )
                db.add(vote)
            
            # 8. Marquer l'utilisateur comme ayant voté
            voter.has_voted = True
            voter.current_exam_period = exam_period.id
            
            db.commit()
            
            # 9. Message de confirmation
            vote_list = "\n".join([f"• {user.mention}" for user in voted_users])
            
            embed = discord.Embed(
                title="✅ Votes Enregistrés !",
                description=f"Tu as voté pour {len(voted_users)} personne(s) :",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="👥 Tes Votes",
                value=vote_list,
                inline=False
            )
            
            embed.add_field(
                name="🎯 Prochaine Étape",
                value="Tu peux maintenant passer ton examen !\n"
                      "Les bonus seront calculés et appliqués à la fin des 6h.",
                inline=False
            )
            
            embed.set_footer(text=f"Période d'examen : {exam_period.id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            print(f"✅ {interaction.user.name} a voté pour {len(voted_users)} personne(s)")
        
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur vote: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Erreur lors du vote : {e}",
                ephemeral=True
            )
        
        finally:
            db.close()
    
    def get_vote_counts(self, exam_period_id: str) -> dict:
        """
        Compte les votes reçus par chaque utilisateur
        
        Returns:
            dict: {user_id: vote_count}
        """
        db = SessionLocal()
        try:
            votes = db.query(
                Vote.voted_for_id,
                func.count(Vote.id).label('vote_count')
            ).filter(
                Vote.exam_period_id == exam_period_id
            ).group_by(
                Vote.voted_for_id
            ).all()
            
            return {user_id: count for user_id, count in votes}
        
        finally:
            db.close()
    
    def calculate_bonus(self, vote_count: int) -> tuple:
        """
        Calcule le bonus en fonction du nombre de votes
        
        Returns:
            tuple: (bonus_points, bonus_level)
        """
        if vote_count >= 8:
            return 20.0, "or"
        elif vote_count >= 5:
            return 12.0, "argent"
        elif vote_count >= 3:
            return 6.0, "bronze"
        else:
            return 0.0, None


# ==================== COMMANDE DISCORD /vote ====================
# À ajouter dans bot.py

@bot.tree.command(name="vote", description="Voter pour 1 à 3 personnes qui t'ont aidé")
@app_commands.describe(
    user1="Première personne à récompenser",
    user2="Deuxième personne à récompenser (optionnel)",
    user3="Troisième personne à récompenser (optionnel)"
)
async def vote(
    interaction: discord.Interaction,
    user1: discord.Member,
    user2: discord.Member = None,
    user3: discord.Member = None
):
    """Commande pour voter"""
    vote_system = VoteSystem(bot)
    await vote_system.vote_command(interaction, user1, user2, user3)


# ==================== COMMANDE ADMIN : Créer une période d'examen ====================
# À ajouter dans bot.py

@bot.tree.command(name="create_exam_period", description="[ADMIN] Créer une période d'examen de 6h")
@commands.has_permissions(administrator=True)
@app_commands.describe(
    group="Numéro du groupe (1-5)",
    start_time="Date et heure de début (format: YYYY-MM-DD HH:MM)"
)
async def create_exam_period(
    interaction: discord.Interaction,
    group: int,
    start_time: str
):
    """Crée une période d'examen de 6h"""
    await interaction.response.defer(ephemeral=True)
    
    from datetime import datetime, timedelta
    from db_connection import SessionLocal
    from models import ExamPeriod
    
    try:
        # Parser la date
        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        end = start + timedelta(hours=6)
        
        # Générer l'ID
        period_id = f"{start.strftime('%Y-%m-%d')}_group{group}"
        
        # Créer la période
        db = SessionLocal()
        try:
            period = ExamPeriod(
                id=period_id,
                group_number=group,
                start_time=start,
                end_time=end,
                votes_closed=False,
                bonuses_applied=False
            )
            
            db.add(period)
            db.commit()
            
            embed = discord.Embed(
                title="✅ Période d'Examen Créée",
                color=discord.Color.green()
            )
            
            embed.add_field(name="🆔 ID", value=period_id, inline=False)
            embed.add_field(name="📊 Groupe", value=f"Niveau {group}", inline=True)
            embed.add_field(name="⏰ Début", value=start.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="🏁 Fin", value=end.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(
                name="ℹ️ Info",
                value="Les votes sont ouverts pendant toute la période.\n"
                      "Les bonus seront appliqués automatiquement à la fin.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        finally:
            db.close()
    
    except ValueError:
        await interaction.followup.send(
            "❌ Format de date incorrect. Utilise : YYYY-MM-DD HH:MM\n"
            "Exemple : 2026-01-20 09:00",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Erreur : {e}",
            ephemeral=True
        )


# ==================== COMMANDE POUR VÉRIFIER SON STATUT DE VOTE ====================
# À ajouter dans bot.py

@bot.tree.command(name="my_vote_status", description="Vérifier si tu as voté")
async def my_vote_status(interaction: discord.Interaction):
    """Vérifie si l'utilisateur a voté"""
    await interaction.response.defer(ephemeral=True)
    
    from db_connection import SessionLocal
    from models import Utilisateur, Vote, ExamPeriod
    
    db = SessionLocal()
    try:
        user = db.query(Utilisateur).filter(
            Utilisateur.user_id == interaction.user.id
        ).first()
        
        if not user:
            await interaction.followup.send(
                "❌ Tu n'es pas inscrit. Utilise `/register`",
                ephemeral=True
            )
            return
        
        # Période active
        vote_system = VoteSystem(bot)
        exam_period = vote_system.get_active_exam_period(user.niveau_actuel)
        
        if not exam_period:
            await interaction.followup.send(
                "ℹ️ Aucune période d'examen active pour ton groupe.",
                ephemeral=True
            )
            return
        
        # Vérifier votes
        votes = db.query(Vote).filter(
            Vote.voter_id == interaction.user.id,
            Vote.exam_period_id == exam_period.id
        ).all()
        
        if len(votes) == 0:
            embed = discord.Embed(
                title="⚠️ Tu n'as pas encore voté",
                description=f"Tu dois voter avant de passer l'examen !",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📝 Comment voter ?",
                value="Utilise la commande `/vote @user1 @user2 @user3`\n"
                      "Tu peux voter pour 1 à 3 personnes maximum.",
                inline=False
            )
        else:
            voted_for = []
            for vote in votes:
                member = interaction.guild.get_member(vote.voted_for_id)
                if member:
                    voted_for.append(f"• {member.mention}")
            
            embed = discord.Embed(
                title="✅ Tu as déjà voté",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name=f"👥 Tes Votes ({len(votes)})",
                value="\n".join(voted_for),
                inline=False
            )
            
            embed.add_field(
                name="🎯 Prochaine étape",
                value="Tu peux passer l'examen quand tu veux pendant les 6h !",
                inline=False
            )
        
        embed.set_footer(text=f"Période : {exam_period.id}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    finally:
        db.close()
