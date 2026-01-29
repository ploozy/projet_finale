"""
Système de Vote pour Récompense d'Entraide
⚠️ ATTENTION : Ne pas mettre de @bot.tree.command ici.
La commande doit être enregistrée dans bot.py qui appellera la méthode vote_command de ce fichier.
"""

import discord
from datetime import datetime
from sqlalchemy import func
from db_connection import SessionLocal
from models import Utilisateur, Vote, ExamPeriod
import traceback

class VoteSystem:
    """Gestion du système de vote et des bonus"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_active_exam_period(self, group_number: int):
        """Récupère la période d'examen active pour un groupe (votes 24h avant)"""
        db = SessionLocal()
        try:
            now = datetime.now()
            # Cherche une période active : votes ouverts (24h avant), pas encore fermés
            period = db.query(ExamPeriod).filter(
                ExamPeriod.group_number == group_number,
                ExamPeriod.vote_start_time <= now,  # Votes ouverts 24h avant
                ExamPeriod.end_time >= now,  # Pas encore finie
                ExamPeriod.votes_closed == False
            ).first()
            return period
        finally:
            db.close()
    
    async def vote_command(
        self, 
        interaction: discord.Interaction, 
        user1: discord.Member,
        user2: discord.Member = None,
        user3: discord.Member = None
    ):
        """
        Logique principale de la commande /vote.
        À appeler depuis bot.py.
        """
        # On diffère la réponse car les opérations DB peuvent prendre > 3s
        await interaction.response.defer(ephemeral=True)
        
        db = SessionLocal()
        try:
            voter_id = interaction.user.id
            
            # 1. Vérifier que l'utilisateur est inscrit
            voter = db.query(Utilisateur).filter(Utilisateur.user_id == voter_id).first()
            if not voter:
                await interaction.followup.send("❌ Tu dois d'abord t'inscrire avec `/register`", ephemeral=True)
                return

            # 2. Vérifier qu'il y a un examen en cours pour son groupe
            exam_period = self.get_active_exam_period(voter.niveau_actuel)
            if not exam_period:
                await interaction.followup.send("❌ Aucune période de vote/examen active pour ton groupe actuellement.", ephemeral=True)
                return

            # 3. Vérifier s'il a déjà voté pour cet examen spécifique
            existing_votes = db.query(Vote).filter(
                Vote.voter_id == voter_id,
                Vote.exam_period_id == exam_period.id
            ).count()
            
            if existing_votes > 0:
                await interaction.followup.send("❌ Tu as déjà voté pour cette session d'examen !", ephemeral=True)
                return
            
            # 4. Filtrer les utilisateurs valides (ignorer les None)
            potential_votes = [u for u in [user1, user2, user3] if u is not None]
            
            # Dédoublonner si l'utilisateur a mis 2 fois la même personne
            voted_users_unique = list(set(potential_votes))

            # Minimum 1 vote requis (pour les tests)
            if len(voted_users_unique) < 1:
                await interaction.followup.send("❌ Tu dois voter pour au moins 1 personne.", ephemeral=True)
                return

            # 5. Vérifications sur les candidats
            errors = []
            valid_targets = []
            
            for target_member in voted_users_unique:
                # A. Pas de vote pour soi-même
                if target_member.id == voter_id:
                    errors.append(f"❌ Tu ne peux pas voter pour toi-même ({target_member.mention}).")
                    continue
                
                # B. Le candidat est-il inscrit dans la DB ?
                target_db = db.query(Utilisateur).filter(Utilisateur.user_id == target_member.id).first()
                if not target_db:
                    errors.append(f"❌ {target_member.mention} n'est pas inscrit dans le système.")
                    continue
                
                # C. Le candidat est-il dans le même groupe ?
                if target_db.niveau_actuel != voter.niveau_actuel:
                    errors.append(f"❌ {target_member.mention} n'est pas dans ton groupe (Groupe {voter.niveau_actuel}).")
                    continue
                
                valid_targets.append(target_db)
            
            # Si erreurs, on arrête tout
            if errors:
                await interaction.followup.send("\n".join(errors), ephemeral=True)
                return
            
            # 6. Enregistrement des votes
            for target in valid_targets:
                new_vote = Vote(
                    voter_id=voter.user_id,
                    voted_for_id=target.user_id,
                    exam_period_id=exam_period.id,
                    date=datetime.now()
                )
                db.add(new_vote)

            # 7. Marquer le votant comme ayant participé
            voter.has_voted = True
            voter.current_exam_period = exam_period.id
            
            db.commit()
            
            # 8. Réponse positive
            mentions = " ".join([f"<@{u.user_id}>" for u in valid_targets])
            embed = discord.Embed(
                title="✅ Votes enregistrés",
                description=f"Merci pour ton entraide ! Tes votes ont été comptabilisés pour :\n{mentions}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Tu peux maintenant accéder à l'examen.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur critique dans vote_command: {e}")
            traceback.print_exc()
            await interaction.followup.send("Une erreur interne est survenue lors du vote.", ephemeral=True)
        finally:
            db.close()

    def get_vote_counts(self, exam_period_id: int) -> dict:
        """Retourne un dictionnaire {user_id: nombre_votes} pour un examen donné"""
        db = SessionLocal()
        try:
            results = db.query(
                Vote.voted_for_id, 
                func.count(Vote.id)
            ).filter(
                Vote.exam_period_id == exam_period_id
            ).group_by(Vote.voted_for_id).all()
            
            return {user_id: count for user_id, count in results}
        finally:
            db.close()

    def calculate_bonus(self, vote_count: int):
        """
        Calcule le bonus selon les paliers définis :
        - Or (7+) : 10%
        - Argent (4-6) : 8%
        - Bronze (1-3) : 5%
        """
        if vote_count >= 7:
            return 10.0, "Or 🥇"
        elif vote_count >= 4:
            return 8.0, "Argent 🥈"
        elif vote_count >= 1:
            return 5.0, "Bronze 🥉"
        else:
            return 0.0, None
