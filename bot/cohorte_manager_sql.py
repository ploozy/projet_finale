"""
Gestionnaire de cohortes avec PostgreSQL et système de groupes
Gère les inscriptions, passages de niveau et réaffectations
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from models import Cohorte, Utilisateur, CalendrierExamen, HistoriqueCohorte
from db_connection import SessionLocal

class CohortManagerSQL:
    """Gestionnaire de cohortes temporelles avec PostgreSQL"""

    def __init__(self):
        self.config = {
            'max_membres_par_groupe': 15,
            'jours_avant_fermeture': 14,
            'delai_entre_examens_jours': 14,
            'niveau_max': 5,
            'duree_tranche_examen_heures': 6  # Tranche de 6h pour passer l'examen
        }

    def _generate_cohort_id(self, db: Session) -> str:
        """Génère un ID de cohorte unique (ex: JAN26-A)"""
        now = datetime.now()
        month = now.strftime('%b').upper()[:3]  # JAN, FEB, MAR...
        year = now.strftime('%y')  # 26, 27...

        existing_ids = [c[0] for c in db.query(Cohorte.id).all()]

        letter = 'A'
        base_id = f"{month}{year}"
        while f"{base_id}-{letter}" in existing_ids:
            letter = chr(ord(letter) + 1)

        return f"{base_id}-{letter}"

    def _generate_exam_calendar(self, cohorte_id: str, first_exam_date: datetime, db: Session):
        """Génère le calendrier d'examens avec tranches horaires de 6h"""
        calendrier = []

        for niveau in range(1, self.config['niveau_max'] + 1):
            # Date de début de l'examen
            date_debut = first_exam_date + timedelta(
                days=self.config['delai_entre_examens_jours'] * (niveau - 1)
            )

            # Date de fin (6h après le début)
            date_fin = date_debut + timedelta(hours=self.config['duree_tranche_examen_heures'])

            cal_entry = CalendrierExamen(
                cohorte_id=cohorte_id,
                niveau=niveau,
                exam_id=niveau,  # Correspond aux examens dans exam.json
                date_debut=date_debut,
                date_fin=date_fin
            )
            calendrier.append(cal_entry)

        return calendrier

    def create_cohort(self, first_exam_date=None) -> str:
        """Crée une nouvelle cohorte avec son calendrier d'examens"""
        db = SessionLocal()
        try:
            if first_exam_date is None:
                # Par défaut, premier examen dans 14 jours à 9h00
                first_exam_date = datetime.now() + timedelta(days=14)
                first_exam_date = first_exam_date.replace(hour=9, minute=0, second=0, microsecond=0)

            cohort_id = self._generate_cohort_id(db)

            new_cohort = Cohorte(
                id=cohort_id,
                date_creation=datetime.now(),
                date_premier_examen=first_exam_date,
                niveau_actuel=1,
                statut='en_formation'
            )

            db.add(new_cohort)
            db.flush()

            # Créer le calendrier avec tranches horaires
            calendrier = self._generate_exam_calendar(cohort_id, first_exam_date, db)
            for cal_entry in calendrier:
                db.add(cal_entry)

            db.commit()
            print(f"✅ Cohorte {cohort_id} créée avec succès")
            return cohort_id

        except Exception as e:
            db.rollback()
            print(f"❌ Erreur create_cohort: {e}")
            raise
        finally:
            db.close()

    def get_active_formation_cohort(self) -> Cohorte:
        """
        Récupère la cohorte en formation (acceptant des inscriptions)
        Crée une nouvelle cohorte si aucune n'est disponible
        """
        db = SessionLocal()
        try:
            cohortes = db.query(Cohorte).filter(
                Cohorte.statut == 'en_formation'
            ).all()

            for cohort in cohortes:
                membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                    Utilisateur.cohorte_id == cohort.id
                ).scalar()

                days_old = (datetime.now() - cohort.date_creation).days

                if (membres_count < self.config['max_membres_par_groupe'] * 3 and  # Max 3 groupes initiaux
                    days_old < self.config['jours_avant_fermeture']):
                    return cohort
                else:
                    self._close_cohort(cohort.id, db)

            db.close()
            cohort_id = self.create_cohort()

            db = SessionLocal()
            return db.query(Cohorte).filter(Cohorte.id == cohort_id).first()
        finally:
            db.close()

    def _close_cohort(self, cohort_id: str, db: Session = None):
        """Ferme une cohorte (passe en statut 'active')"""
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True

        try:
            cohort = db.query(Cohorte).filter(Cohorte.id == cohort_id).first()
            if cohort:
                cohort.statut = 'active'
                cohort.date_fermeture = datetime.now()
                db.commit()
                print(f"🔒 Cohorte {cohort_id} fermée et active")
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur _close_cohort: {e}")
            raise
        finally:
            if should_close_db:
                db.close()

    def add_user_to_cohort(self, user_id: int, username: str) -> tuple:
        """
        Ajoute un utilisateur à une cohorte avec attribution automatique du sous-groupe
        Returns: (cohorte_id, niveau_actuel, sous_groupe)
        """
        db = SessionLocal()
        try:
            existing_user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()

            if existing_user:
                print(f"ℹ️ Utilisateur {username} déjà inscrit")
                return (existing_user.cohorte_id, existing_user.niveau_actuel, existing_user.sous_groupe)

            cohort = self.get_active_formation_cohort()

            # Déterminer le sous-groupe (A, B, C, etc.)
            sous_groupe = self._get_next_available_sous_groupe(cohort.id, 1, db)

            new_user = Utilisateur(
                user_id=user_id,
                username=username,
                cohorte_id=cohort.id,
                niveau_actuel=1,
                sous_groupe=sous_groupe,
                examens_reussis=0,
                date_inscription=datetime.now()
            )

            db.add(new_user)

            historique = HistoriqueCohorte(
                user_id=user_id,
                cohorte_id=cohort.id,
                date_ajout=datetime.now()
            )
            db.add(historique)

            db.commit()
            print(f"✅ {username} ajouté à la cohorte {cohort.id} - Groupe {1}{sous_groupe}")
            return (cohort.id, 1, sous_groupe)

        except Exception as e:
            db.rollback()
            print(f"❌ Erreur add_user_to_cohort: {e}")
            raise
        finally:
            db.close()

    def _get_next_available_sous_groupe(self, cohorte_id: str, niveau: int, db: Session) -> str:
        """
        Trouve le prochain sous-groupe disponible pour un niveau
        Crée un nouveau sous-groupe si tous sont pleins (>= 15 membres)
        """
        # Compter les membres par sous-groupe pour ce niveau
        users_by_group = db.query(
            Utilisateur.sous_groupe,
            func.count(Utilisateur.user_id).label('count')
        ).filter(
            and_(
                Utilisateur.cohorte_id == cohorte_id,
                Utilisateur.niveau_actuel == niveau
            )
        ).group_by(Utilisateur.sous_groupe).all()

        # Créer un dictionnaire {sous_groupe: count}
        group_counts = {g[0]: g[1] for g in users_by_group}

        # Chercher le premier groupe non plein
        letter = 'A'
        while True:
            if letter not in group_counts or group_counts[letter] < self.config['max_membres_par_groupe']:
                return letter
            letter = chr(ord(letter) + 1)

            # Sécurité : limiter à Z
            if ord(letter) > ord('Z'):
                return 'A'  # Fallback

    def get_user_info(self, user_id: int) -> dict:
        """Récupère les informations d'un utilisateur"""
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()

            if not user:
                return None

            return {
                'user_id': user.user_id,
                'username': user.username,
                'cohorte_id': user.cohorte_id,
                'niveau_actuel': user.niveau_actuel,
                'sous_groupe': user.sous_groupe,
                'examens_reussis': user.examens_reussis,
                'date_inscription': user.date_inscription.isoformat(),
                'discord_role_id': user.discord_role_id,
                'discord_channel_id': user.discord_channel_id
            }
        finally:
            db.close()

    def get_next_exam_for_user(self, user_id: int) -> dict:
        """Récupère le prochain examen d'un utilisateur avec la tranche horaire"""
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()

            if not user:
                return None

            exam = db.query(CalendrierExamen).filter(
                and_(
                    CalendrierExamen.cohorte_id == user.cohorte_id,
                    CalendrierExamen.niveau == user.niveau_actuel
                )
            ).first()

            if not exam:
                return None

            return {
                'exam_id': exam.exam_id,
                'niveau': exam.niveau,
                'date_debut': exam.date_debut.isoformat(),
                'date_fin': exam.date_fin.isoformat(),
                'duree_minutes': (exam.date_fin - exam.date_debut).seconds // 60
            }
        finally:
            db.close()

    def update_user_after_exam(self, user_id: int, passed: bool) -> tuple:
        """
        Met à jour l'utilisateur après un examen
        Returns: (message, nouveau_niveau, nouveau_sous_groupe)
        """
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()

            if not user:
                return ("❌ Utilisateur introuvable", None, None)

            old_niveau = user.niveau_actuel
            old_sous_groupe = user.sous_groupe

            if passed:
                # RÉUSSITE : passage au niveau suivant
                new_niveau = min(user.niveau_actuel + 1, self.config['niveau_max'])
                user.niveau_actuel = new_niveau
                user.examens_reussis += 1

                # Attribution du nouveau sous-groupe pour le nouveau niveau
                new_sous_groupe = self._get_next_available_sous_groupe(
                    user.cohorte_id, new_niveau, db
                )
                user.sous_groupe = new_sous_groupe

                db.commit()
                message = f"✅ Félicitations ! Niveau {old_niveau}{old_sous_groupe} → {new_niveau}{new_sous_groupe}"
                return (message, new_niveau, new_sous_groupe)

            else:
                # ÉCHEC : reste dans le même niveau mais garde son sous-groupe
                # Les places se libèrent avec les réussites
                db.commit()
                message = f"❌ Examen non réussi - Vous restez en Groupe {old_niveau}{old_sous_groupe}. Repassez l'examen à la prochaine session."
                return (message, old_niveau, old_sous_groupe)

        except Exception as e:
            db.rollback()
            print(f"❌ Erreur update_user_after_exam: {e}")
            raise
        finally:
            db.close()

    def update_user_discord_info(self, user_id: int, role_id: int, channel_id: int):
        """Met à jour les informations Discord de l'utilisateur"""
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()

            if user:
                user.discord_role_id = role_id
                user.discord_channel_id = channel_id
                db.commit()
                print(f"✅ Info Discord mise à jour pour user {user_id}")
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur update_user_discord_info: {e}")
        finally:
            db.close()

    def get_cohort_members(self, cohort_id: str) -> list:
        """Récupère les membres d'une cohorte"""
        db = SessionLocal()
        try:
            users = db.query(Utilisateur).filter(
                Utilisateur.cohorte_id == cohort_id
            ).all()

            return [{
                'user_id': u.user_id,
                'username': u.username,
                'niveau_actuel': u.niveau_actuel,
                'sous_groupe': u.sous_groupe,
                'examens_reussis': u.examens_reussis
            } for u in users]
        finally:
            db.close()

    def get_all_cohortes(self) -> list:
        """Récupère toutes les cohortes"""
        db = SessionLocal()
        try:
            cohortes = db.query(Cohorte).all()
            result = []

            for cohort in cohortes:
                membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                    Utilisateur.cohorte_id == cohort.id
                ).scalar()

                result.append({
                    'id': cohort.id,
                    'date_creation': cohort.date_creation.isoformat(),
                    'statut': cohort.statut,
                    'niveau_actuel': cohort.niveau_actuel,
                    'membres_count': membres_count
                })

            return result
        finally:
            db.close()
