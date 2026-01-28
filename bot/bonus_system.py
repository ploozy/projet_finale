"""
Système d'Application des Bonus
S'exécute automatiquement à la fin de chaque période d'examen (6h)
Utilise APScheduler pour planifier l'application des bonus exactement à end_time
"""

import discord
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from db_connection import SessionLocal
from models import Utilisateur, Vote, ExamPeriod, ExamResult
from vote_system import VoteSystem
from sqlalchemy import func

# Scheduler global pour les applications de bonus
bonus_scheduler = AsyncIOScheduler()


class BonusSystem:
    """Gestion de l'application des bonus"""
    
    def __init__(self, bot):
        self.bot = bot
        self.vote_system = VoteSystem(bot)
    
    async def apply_bonuses_for_period(self, exam_period: ExamPeriod, guild: discord.Guild):
        """
        Applique les bonus pour une période d'examen terminée
        
        1. Calcule les votes reçus par chaque utilisateur
        2. Attribue les niveaux de bonus (Or/Argent/Bronze)
        3. Applique les bonus aux notes d'examen
        4. Vérifie les promotions (échec → réussite)
        5. Envoie les notifications
        """
        db = SessionLocal()
        
        try:
            print(f"\n{'='*60}")
            print(f"🎁 APPLICATION DES BONUS - {exam_period.id}")
            print(f"{'='*60}\n")
            
            # 1. Récupérer tous les votes
            vote_counts = self.vote_system.get_vote_counts(exam_period.id)
            
            print(f"📊 Votes comptabilisés : {len(vote_counts)} utilisateur(s)")
            
            # 2. Attribuer les bonus et calculer les rangs
            bonus_assignments = {}

            # Trier par nombre de votes (décroissant) pour calculer les rangs
            sorted_votes = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)

            for rank, (user_id, vote_count) in enumerate(sorted_votes, start=1):
                bonus_points, bonus_level = self.vote_system.calculate_bonus(vote_count)
                bonus_assignments[user_id] = {
                    'votes': vote_count,
                    'bonus': bonus_points,
                    'level': bonus_level,
                    'rank': rank,
                    'total_voters': len(sorted_votes)
                }

                # Mettre à jour l'utilisateur
                user = db.query(Utilisateur).filter(
                    Utilisateur.user_id == user_id
                ).first()

                if user:
                    user.bonus_points = bonus_points
                    user.bonus_level = bonus_level

                    print(f"  ✅ {user.username}: {vote_count} votes (rang #{rank}) → +{bonus_points}% ({bonus_level})")

            db.commit()
            
            # 3. Récupérer tous les résultats d'examen de cette période
            start_time = exam_period.start_time
            end_time = exam_period.end_time
            
            exam_results = db.query(ExamResult).filter(
                ExamResult.date >= start_time,
                ExamResult.date <= end_time
            ).all()
            
            print(f"\n📝 Résultats d'examen trouvés : {len(exam_results)}")
            
            promotions = []
            notifications = []
            
            # 4. Appliquer les bonus aux notes
            for result in exam_results:
                user = db.query(Utilisateur).filter(
                    Utilisateur.user_id == result.user_id
                ).first()
                
                if not user or user.bonus_points == 0:
                    continue
                
                # Note originale
                original_percentage = result.percentage
                
                # Appliquer le bonus (additif)
                bonus_percentage = original_percentage + user.bonus_points
                
                # Cap à 100%
                bonus_percentage = min(bonus_percentage, 100.0)
                
                # Vérifier si le bonus fait passer de raté à réussi
                was_failed = original_percentage < result.passing_score
                is_now_passed = bonus_percentage >= result.passing_score
                
                print(f"\n  👤 {user.username}:")
                print(f"     Note originale: {original_percentage}%")
                print(f"     Bonus: +{user.bonus_points}%")
                print(f"     Note finale: {bonus_percentage}%")
                
                if was_failed and is_now_passed:
                    print(f"     🎉 PROMOTION: {original_percentage}% → {bonus_percentage}% (≥{result.passing_score}%)")
                    
                    # Promouvoir l'utilisateur
                    old_niveau = user.niveau_actuel
                    old_groupe = user.groupe
                    
                    # Trouver un groupe disponible au niveau supérieur
                    new_niveau = old_niveau + 1
                    new_groupe = await self._find_available_group(guild, new_niveau, db)
                    
                    user.niveau_actuel = new_niveau
                    user.groupe = new_groupe
                    user.examens_reussis += 1
                    
                    promotions.append({
                        'user_id': user.user_id,
                        'old_groupe': old_groupe,
                        'new_groupe': new_groupe,
                        'old_percentage': original_percentage,
                        'new_percentage': bonus_percentage,
                        'bonus': user.bonus_points,
                        'bonus_level': user.bonus_level
                    })
                    
                    print(f"     ✅ Promotion: {old_groupe} → {new_groupe}")
                
                # Sauvegarder la notification avec votes et rang
                bonus_info = bonus_assignments.get(user.user_id, {})
                notifications.append({
                    'user_id': user.user_id,
                    'original_percentage': original_percentage,
                    'bonus_percentage': bonus_percentage,
                    'bonus': user.bonus_points,
                    'bonus_level': user.bonus_level,
                    'promoted': was_failed and is_now_passed,
                    'votes_received': bonus_info.get('votes', 0),
                    'rank': bonus_info.get('rank', 0),
                    'total_voters': bonus_info.get('total_voters', 0)
                })
                
                # Réinitialiser le bonus (crédit unique)
                user.bonus_points = 0.0
                user.bonus_level = None
                user.has_voted = False
                user.current_exam_period = None
            
            db.commit()
            
            # 5. Envoyer les notifications Discord
            print(f"\n📧 Envoi de {len(notifications)} notification(s)...")
            
            for notif in notifications:
                await self._send_bonus_notification(notif, guild)
            
            # 6. Gérer les promotions (rôles Discord)
            print(f"\n🎊 Gestion de {len(promotions)} promotion(s)...")

            for promo in promotions:
                await self._handle_promotion(promo, guild)

            # 7. [SUPPRIMÉ] Pas de message public dans le salon entraide
            # Les utilisateurs reçoivent uniquement des MPs privés avec leurs votes et rang

            # 8. Marquer la période comme traitée
            exam_period.bonuses_applied = True
            exam_period.votes_closed = True
            db.commit()
            
            print(f"\n{'='*60}")
            print(f"✅ APPLICATION DES BONUS TERMINÉE")
            print(f"{'='*60}\n")
        
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur application bonus: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            db.close()
    
    async def _find_available_group(self, guild: discord.Guild, niveau: int, db) -> str:
        """
        Trouve un groupe disponible (< 15 membres) pour un niveau donné
        Crée un nouveau groupe si tous sont pleins
        """
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        
        for letter in letters:
            groupe_name = f"{niveau}-{letter}"
            role = discord.utils.get(guild.roles, name=f"Groupe {groupe_name}")
            
            if role is None:
                # Groupe n'existe pas, le créer
                await self._create_new_group(guild, groupe_name, db)
                return groupe_name
            
            # Compter les membres du groupe
            member_count = len(role.members)
            
            if member_count < 15:
                return groupe_name
        
        # Si tous les groupes A-J sont pleins, créer K
        new_groupe = f"{niveau}-K"
        await self._create_new_group(guild, new_groupe, db)
        return new_groupe
    
    async def _create_new_group(self, guild: discord.Guild, groupe: str, db):
        """Crée un nouveau groupe (rôle + salons)"""
        from onboarding import OnboardingManager
        
        print(f"  🆕 Création du groupe {groupe}...")
        
        onboarding = OnboardingManager(self.bot)
        
        # Créer le rôle
        role = await onboarding._get_or_create_role(guild, groupe)
        
        # Créer les salons
        await onboarding._create_group_channels(guild, groupe, role)
        
        print(f"  ✅ Groupe {groupe} créé")
    
    async def _send_bonus_notification(self, notif: dict, guild: discord.Guild):
        """Envoie une notification de bonus à un utilisateur"""
        try:
            member = guild.get_member(notif['user_id'])
            
            if not member:
                print(f"  ⚠️ Membre {notif['user_id']} introuvable")
                return
            
            bonus_emoji = {
                'or': '🥇',
                'argent': '🥈',
                'bronze': '🥉'
            }.get(notif['bonus_level'], '🎁')
            
            bonus_color = {
                'or': discord.Color.gold(),
                'argent': discord.Color.greyple(),
                'bronze': discord.Color.orange()
            }.get(notif['bonus_level'], discord.Color.blue())
            
            # Afficher le rang avec emoji
            rank_emoji = "🥇" if notif.get('rank', 0) == 1 else "🥈" if notif.get('rank', 0) == 2 else "🥉" if notif.get('rank', 0) == 3 else "🏅"

            embed = discord.Embed(
                title=f"{bonus_emoji} Bonus d'Entraide Appliqué !",
                description=f"Tes camarades ont voté pour toi !",
                color=bonus_color,
                timestamp=datetime.now()
            )

            # Nombre de votes reçus
            embed.add_field(
                name="🗳️ Votes Reçus",
                value=f"**{notif.get('votes_received', 0)} vote(s)**",
                inline=True
            )

            # Rang
            embed.add_field(
                name=f"{rank_emoji} Rang",
                value=f"**#{notif.get('rank', 0)}** / {notif.get('total_voters', 0)}",
                inline=True
            )

            if notif['bonus_level']:
                embed.add_field(
                    name="🏆 Niveau de Récompense",
                    value=f"**{notif['bonus_level'].upper()}** ({bonus_emoji})",
                    inline=True
                )

            embed.add_field(
                name="📊 Bonus Obtenu",
                value=f"**+{notif['bonus']}%**",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Application",
                value=f"**{notif['original_percentage']}%** → **{notif['bonus_percentage']}%**",
                inline=True
            )
            
            if notif['promoted']:
                embed.add_field(
                    name="🎉 PROMOTION !",
                    value="Grâce au bonus, tu as réussi l'examen !\n"
                          "Tu passes au niveau suivant ! 🚀",
                    inline=False
                )
                embed.color = discord.Color.green()
            
            embed.add_field(
                name="💡 Info",
                value="Ce bonus était valable uniquement pour cet examen.\n"
                      "Continue à aider tes camarades pour gagner plus de bonus !",
                inline=False
            )
            
            await member.send(embed=embed)
            print(f"  ✅ Notification envoyée à {member.name}")
        
        except discord.Forbidden:
            print(f"  ⚠️ MP bloqués pour {notif['user_id']}")
        except Exception as e:
            print(f"  ❌ Erreur notification {notif['user_id']}: {e}")
    
    async def _handle_promotion(self, promo: dict, guild: discord.Guild):
        """Gère la promotion d'un utilisateur (changement de rôles Discord)"""
        try:
            member = guild.get_member(promo['user_id'])
            
            if not member:
                print(f"  ⚠️ Membre {promo['user_id']} introuvable")
                return
            
            # Retirer l'ancien rôle
            old_role = discord.utils.get(guild.roles, name=f"Groupe {promo['old_groupe']}")
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
                print(f"  ❌ Rôle {old_role.name} retiré de {member.name}")
            
            # Ajouter le nouveau rôle
            new_role = discord.utils.get(guild.roles, name=f"Groupe {promo['new_groupe']}")
            if not new_role:
                # Créer le groupe si nécessaire
                db = SessionLocal()
                try:
                    niveau = int(promo['new_groupe'].split('-')[0])
                    promo['new_groupe'] = await self._find_available_group(guild, niveau, db)
                    new_role = discord.utils.get(guild.roles, name=f"Groupe {promo['new_groupe']}")
                finally:
                    db.close()
            
            if new_role:
                await member.add_roles(new_role)
                print(f"  ✅ Rôle {new_role.name} ajouté à {member.name}")
            
            # Envoyer message de promotion
            bonus_emoji = {
                'or': '🥇',
                'argent': '🥈',
                'bronze': '🥉'
            }.get(promo['bonus_level'], '🎁')
            
            embed = discord.Embed(
                title="🎊 PROMOTION !",
                description=f"Félicitations {member.mention} !",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Progression",
                value=f"**Groupe {promo['old_groupe']}** → **Groupe {promo['new_groupe']}**",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Note",
                value=f"**{promo['old_percentage']}%** (échec)\n"
                      f"+ **{promo['bonus']}%** {bonus_emoji}\n"
                      f"= **{promo['new_percentage']}%** ✅",
                inline=True
            )
            
            embed.add_field(
                name="🏆 Bonus",
                value=f"Niveau **{promo['bonus_level'].upper()}**",
                inline=True
            )
            
            embed.add_field(
                name="🚀 Prochaine Étape",
                value=f"Accède aux salons du Groupe {promo['new_groupe']} !\n"
                      f"Continue comme ça ! 💪",
                inline=False
            )
            
            await member.send(embed=embed)
            print(f"  🎉 Message de promotion envoyé à {member.name}")
        
        except discord.Forbidden:
            print(f"  ⚠️ MP bloqués pour {promo['user_id']}")
        except Exception as e:
            print(f"  ❌ Erreur promotion {promo['user_id']}: {e}")

    async def _send_group_summary(self, exam_period: ExamPeriod, notifications: list, guild: discord.Guild, db):
        """Envoie un récapitulatif des résultats dans le salon discussion du groupe"""
        try:
            # Trouver le numéro de groupe
            group_number = exam_period.group_number

            # Nom du salon : groupe-X-Y-entraide (ex: groupe-1-a-entraide)
            # On doit trouver tous les groupes de ce niveau
            possible_groups = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']

            for letter in possible_groups:
                channel_name = f"groupe-{group_number}-{letter}-entraide"
                channel = discord.utils.get(guild.text_channels, name=channel_name)

                if channel:
                    # Filtrer les notifications pour ce groupe seulement
                    group_notifications = []
                    for notif in notifications:
                        user = db.query(Utilisateur).filter(Utilisateur.user_id == notif['user_id']).first()
                        if user and user.niveau_actuel == group_number:
                            group_notifications.append({**notif, 'username': user.username})

                    if not group_notifications:
                        continue  # Pas de résultats pour ce groupe

                    # Créer l'embed récapitulatif
                    embed = discord.Embed(
                        title=f"📊 Résultats de l'Examen - Groupe {group_number}-{letter.upper()}",
                        description=f"Voici les résultats de la période d'examen qui vient de se terminer !",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )

                    # Ajouter chaque résultat
                    for notif in group_notifications:
                        bonus_emoji = {
                            'Or': '🥇',
                            'Argent': '🥈',
                            'Bronze': '🥉'
                        }.get(notif.get('bonus_level', ''), '')

                        bonus_text = f"+{notif['bonus']}% {bonus_emoji}" if notif['bonus'] > 0 else "Aucun bonus"

                        result_text = (
                            f"**Note originale:** {notif['original_percentage']}%\n"
                            f"**Bonus:** {bonus_text}\n"
                            f"**Note finale:** {notif['bonus_percentage']}%\n"
                        )

                        if notif.get('promoted'):
                            result_text += "🎉 **PROMOTION !**\n"

                        embed.add_field(
                            name=f"👤 {notif['username']}",
                            value=result_text,
                            inline=False
                        )

                    embed.set_footer(text="Félicitations à tous ! Continuez comme ça ! 💪")

                    await channel.send(embed=embed)
                    print(f"  ✅ Récapitulatif envoyé dans {channel_name}")

        except Exception as e:
            print(f"  ❌ Erreur envoi récapitulatif groupe: {e}")
            import traceback
            traceback.print_exc()


# ==================== FONCTIONS DE PLANIFICATION ====================

async def apply_bonuses_job(bot, exam_period_id: str):
    """
    Job APScheduler : Applique les bonus pour une période d'examen terminée
    S'exécute automatiquement à end_time
    """
    db = SessionLocal()
    try:
        # Récupérer la période
        period = db.query(ExamPeriod).filter(ExamPeriod.id == exam_period_id).first()

        if not period:
            print(f"❌ Période {exam_period_id} introuvable")
            return

        if period.bonuses_applied:
            print(f"⚠️ Bonus déjà appliqués pour {exam_period_id}")
            return

        # Récupérer le guild
        guild = bot.guilds[0] if bot.guilds else None

        if not guild:
            print(f"❌ Aucun serveur Discord disponible")
            return

        print(f"\n🔔 Application automatique des bonus pour {exam_period_id}")

        # Appliquer les bonus
        bonus_system = BonusSystem(bot)
        await bonus_system.apply_bonuses_for_period(period, guild)

    except Exception as e:
        print(f"❌ Erreur apply_bonuses_job pour {exam_period_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def schedule_bonus_application(bot, exam_period: ExamPeriod):
    """
    Planifie l'application des bonus pour une période d'examen

    Args:
        bot: Instance du bot Discord
        exam_period: Période d'examen pour laquelle planifier les bonus
    """
    # Vérifier que la période n'est pas déjà terminée
    if datetime.now() >= exam_period.end_time:
        print(f"⚠️ Période {exam_period.id} déjà terminée, application immédiate")
        # Exécuter immédiatement dans une coroutine
        import asyncio
        asyncio.create_task(apply_bonuses_job(bot, exam_period.id))
        return

    # Planifier l'application à end_time
    trigger = DateTrigger(run_date=exam_period.end_time)

    bonus_scheduler.add_job(
        apply_bonuses_job,
        trigger=trigger,
        args=[bot, exam_period.id],
        id=f"bonus_{exam_period.id}",
        replace_existing=True,
        misfire_grace_time=3600  # 1h de tolérance si le bot était éteint
    )

    print(f"⏰ Application des bonus planifiée pour {exam_period.id} à {exam_period.end_time.strftime('%Y-%m-%d %H:%M')}")


def start_bonus_scheduler():
    """Démarre le scheduler de bonus"""
    if not bonus_scheduler.running:
        bonus_scheduler.start()
        print("✅ Planificateur de bonus démarré")


def load_pending_exam_periods(bot):
    """
    Charge toutes les périodes d'examen non-terminées au démarrage
    et planifie automatiquement l'application des bonus
    """
    db = SessionLocal()
    try:
        now = datetime.now()

        # Trouver les périodes non-terminées ou terminées mais non-traitées
        pending_periods = db.query(ExamPeriod).filter(
            ExamPeriod.bonuses_applied == False
        ).all()

        count = 0
        for period in pending_periods:
            # Si la période est déjà terminée mais non-traitée, traiter immédiatement
            if period.end_time <= now:
                print(f"📋 Période {period.id} terminée mais non-traitée, planification immédiate")

            schedule_bonus_application(bot, period)
            count += 1

        print(f"📅 {count} période(s) d'examen chargée(s) au démarrage")

    except Exception as e:
        print(f"❌ Erreur load_pending_exam_periods: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


