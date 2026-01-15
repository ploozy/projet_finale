"""
Système de Vote pour Récompense d'Entraide
⚠️ Les commandes Discord sont dans bot.py, PAS ici
"""

import discord
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
        """Logique de la commande /vote"""
        await interaction.response.defer(ephemeral=True)
        
        db = SessionLocal()
        try:
            voter_id = interaction.user.id
            
            # 1. Vérifier que l'utilisateur existe
            voter = db.query(Utilisateur).filter(
                Utilisateur.user_id == voter_id
            ).first()
            
            if not voter:
                await interaction.followup.send(
                    "❌ Tu dois d'abord t'inscrire avec `/register`",
                    ephemeral=True
                )
                return
            
            # 2. Vérifier période d'examen active
            exam_period = self.get_active_exam_period(voter.niveau_actuel)
            
            if not exam_period:
                await interaction.followup.send(
                    "❌ Aucune période d'examen active pour ton groupe.",
                    ephemeral=True
                )
                return
            
            # 3. Vérifier qu'il n'a pas déjà voté
            existing_votes = db.query(Vote).filter(
                Vote.voter_id == voter_id,
                Vote.exam_period_id == exam_period.id
            ).count()
            
            if existing_votes > 0:
                await interaction.followup.send(
                    f"❌ Tu as déjà voté pour cette période d'examen !",
                    ephemeral=True
                )
                return
            
            # 4. Collecter les votes
            voted_users = [u for u in [user1, user2, user3] if u is not None]
            
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
            
            # 6. Vérifier que tous sont du même groupe
            errors = []
            for user in voted_users:
                user_db = db.query(Utilisateur).filter(
                    Utilisateur.user_id == user.id
                ).first()
                
                if not user_db:
                    errors.append(f"❌ {user.mention} n'est pas inscrit")
                elif user_db.niveau_actuel != voter.niveau_actuel:
                    errors.append(f"❌ {user.mention} n'est pas dans ton groupe")
            
            if errors:
                await interaction.followup.send(
                    "❌ **Erreurs :**\n\n" + "\n".join(errors),
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
            
            # 8. Marquer comme ayant voté
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
            
            embed.add_field(name="👥 Tes Votes", value=vote_list, inline=False)
            embed.add_field(
                name="🎯 Prochaine Étape",
                value="Tu peux maintenant passer ton examen !",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"✅ {interaction.user.name} a voté pour {len(voted_users)} personne(s)")
        
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur vote: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        
        finally:
            db.close()
    
    def get_vote_counts(self, exam_period_id: str) -> dict:
        """Compte les votes reçus par chaque utilisateur"""
        db = SessionLocal()
        try:
            votes = db.query(
                Vote.voted_for_id,
                func.count(Vote.id).label('vote_count')
            ).filter(
                Vote.exam_period_id == exam_period_id
            ).group_by(Vote.voted_for_id).all()
            
            return {user_id: count for user_id, count in votes}
        finally:
            db.close()
    
    def calculate_bonus(self, vote_count: int) -> tuple:
        """Calcule le bonus en fonction du nombre de votes"""
        if vote_count >= 8:
            return 20.0, "or"
        elif vote_count >= 5:
            return 12.0, "argent"
        elif vote_count >= 3:
            return 6.0, "bronze"
        else:
            return 0.0, None
