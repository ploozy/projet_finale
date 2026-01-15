"""
Gestionnaire de cohortes avec PostgreSQL
Remplace l'ancien cohorte_manager.py basé sur JSON
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from models import Cohorte, Utilisateur, CalendrierExamen, HistoriqueCohorte
from db_connection import SessionLocal


class CohortManagerSQL:
    """Gestionnaire de cohortes temporelles avec PostgreSQL"""
    
    def __init__(self):
        self.config = {
            'max_membres_par_cohorte': 15,  # Réduit à 15 pour créer plus de groupes
            'jours_avant_fermeture': 14,
            'delai_entre_examens_jours': 14,
            'niveau_max': 5
        }
    
    def _generate_cohort_id(self, db: Session) -> str:
        """Génère un ID de cohorte unique (ex: JAN26-A)"""
        now = datetime.now()
        month = now.strftime('%b').upper()[:3]  # JAN, FEB, MAR...
        year = now.strftime('%y')  # 26, 27...
        
        # Récupérer les IDs existants
        existing_ids = [c[0] for c in db.query(Cohorte.id).all()]
        
        # Trouver la lettre suivante disponible
        letter = 'A'
        base_id = f"{month}{year}"
        while f"{base_id}-{letter}" in existing_ids:
            letter = chr(ord(letter) + 1)
        
        return f"{base_id}-{letter}"
    
    def _generate_exam_calendar(self, cohorte_id: str, first_exam_date: datetime, db: Session):
        """Génère le calendrier d'examens pour une cohorte"""
        calendrier = []
        
        for niveau in range(1, self.config['niveau_max'] + 1):
            exam_date = first_exam_date + timedelta(
                days=self.config['delai_entre_examens_jours'] * (niveau - 1)
            )
            
            cal_entry = CalendrierExamen(
                cohorte_id=cohorte_id,
                niveau=niveau,
                exam_id=niveau,  # Correspond aux examens dans exam.json
                date_examen=exam_date
            )
            calendrier.append(cal_entry)
        
        return calendrier
    
    def create_cohort(self, first_exam_date=None) -> str:
        """Crée une nouvelle cohorte avec son calendrier d'examens"""
        db = SessionLocal()
        try:
            if first_exam_date is None:
                # Par défaut, premier examen dans 14 jours
                first_exam_date = datetime.now() + timedelta(days=14)
            
            # Générer l'ID
            cohort_id = self._generate_cohort_id(db)
            
            # Créer la cohorte
            new_cohort = Cohorte(
                id=cohort_id,
                date_creation=datetime.now(),
                date_premier_examen=first_exam_date,
                niveau_actuel=1,
                statut='en_formation'
            )
            db.add(new_cohort)
            db.flush()  # Pour obtenir l'ID avant le commit
            
            # Créer le calendrier d'examens
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
    
    def get_active_formation_cohort(self, niveau: int = 1) -> Cohorte:
        """
        Récupère la cohorte en formation pour un niveau donné
        Crée une nouvelle cohorte si aucune n'est disponible
        
        Args:
            niveau: Le niveau de la cohorte recherchée (par défaut 1)
        """
        db = SessionLocal()
        try:
            # Chercher les cohortes en formation pour ce niveau
            cohortes = db.query(Cohorte).filter(
                Cohorte.statut == 'en_formation',
                Cohorte.niveau_actuel == niveau
            ).all()
            
            for cohort in cohortes:
                # Compter les membres
                membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                    Utilisateur.cohorte_id == cohort.id
                ).scalar()
                
                # Calculer l'âge de la cohorte
                days_old = (datetime.now() - cohort.date_creation).days
                
                # Vérifier si elle est encore valide
                if (membres_count < self.config['max_membres_par_cohorte'] and 
                    days_old < self.config['jours_avant_fermeture']):
                    return cohort
                else:
                    # Fermer cette cohorte
                    self._close_cohort(cohort.id, db)
            
            # Aucune cohorte valide trouvée, en créer une nouvelle
            db.close()
            cohort_id = self.create_cohort()
            
            # Rouvrir une session pour récupérer la cohorte
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
        Ajoute un utilisateur à une cohorte
        Retourne: (cohorte_id, niveau_actuel)
        """
        db = SessionLocal()
        try:
            # Vérifier si l'utilisateur existe déjà
            existing_user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()
            
            if existing_user:
                print(f"ℹ️ Utilisateur {username} déjà inscrit dans {existing_user.cohorte_id}")
                return existing_user.cohorte_id, existing_user.niveau_actuel
            
            # Trouver ou créer une cohorte en formation (niveau 1 pour nouveau)
            cohort = self.get_active_formation_cohort(niveau=1)
            
            # Créer l'utilisateur
            new_user = Utilisateur(
                user_id=user_id,
                username=username,
                cohorte_id=cohort.id,
                niveau_actuel=1,
                examens_reussis=0,
                date_inscription=datetime.now()
            )
            db.add(new_user)
            
            # Ajouter à l'historique
            historique = HistoriqueCohorte(
                user_id=user_id,
                cohorte_id=cohort.id,
                date_ajout=datetime.now()
            )
            db.add(historique)
            
            db.commit()
            print(f"✅ {username} ajouté à la cohorte {cohort.id}")
            return cohort.id, 1
        
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur add_user_to_cohort: {e}")
            raise
        finally:
            db.close()
    
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
                'examens_reussis': user.examens_reussis,
                'date_inscription': user.date_inscription.isoformat()
            }
        finally:
            db.close()
    
    def get_cohort_info(self, cohort_id: str) -> dict:
        """Récupère les informations d'une cohorte"""
        db = SessionLocal()
        try:
            cohort = db.query(Cohorte).filter(
                Cohorte.id == cohort_id
            ).first()
            
            if not cohort:
                return None
            
            # Compter les membres
            membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                Utilisateur.cohorte_id == cohort_id
            ).scalar()
            
            return {
                'id': cohort.id,
                'date_creation': cohort.date_creation.isoformat(),
                'date_premier_examen': cohort.date_premier_examen.isoformat(),
                'niveau_actuel': cohort.niveau_actuel,
                'statut': cohort.statut,
                'membres_count': membres_count,
                'guild_id': cohort.guild_id,
                'role_id': cohort.role_id,
                'channel_id': cohort.channel_id
            }
        finally:
            db.close()
    
    def get_next_exam_for_user(self, user_id: int) -> dict:
        """Récupère le prochain examen d'un utilisateur"""
        db = SessionLocal()
        try:
            # Récupérer l'utilisateur
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()
            
            if not user:
                return None
            
            # Récupérer l'examen correspondant au niveau actuel
            exam = db.query(CalendrierExamen).filter(
                CalendrierExamen.cohorte_id == user.cohorte_id,
                CalendrierExamen.niveau == user.niveau_actuel
            ).first()
            
            if not exam:
                return None
            
            return {
                'exam_id': exam.exam_id,
                'date': exam.date_examen.isoformat(),
                'niveau': exam.niveau
            }
        finally:
            db.close()
    
    def update_user_after_exam(self, user_id: int, passed: bool) -> str:
        """
        Met à jour l'utilisateur après un examen
        Retourne un message décrivant l'action effectuée
        """
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(
                Utilisateur.user_id == user_id
            ).first()
            
            if not user:
                return "❌ Utilisateur introuvable"
            
            if passed:
                # Réussite : niveau +1
                old_niveau = user.niveau_actuel
                old_cohorte = user.cohorte_id
                
                user.niveau_actuel = min(user.niveau_actuel + 1, self.config['niveau_max'])
                user.examens_reussis += 1
                
                # Trouver une cohorte pour le nouveau niveau
                new_cohort = self._find_cohort_for_level(user.niveau_actuel, db)
                
                if new_cohort and new_cohort.id != old_cohorte:
                    user.cohorte_id = new_cohort.id
                    
                    # Ajouter à l'historique
                    historique = HistoriqueCohorte(
                        user_id=user_id,
                        cohorte_id=new_cohort.id,
                        date_ajout=datetime.now()
                    )
                    db.add(historique)
                    
                    db.commit()
                    message = f"✅ Félicitations ! Niveau {old_niveau} → {user.niveau_actuel}\n📚 Nouvelle cohorte: {new_cohort.id}"
                else:
                    db.commit()
                    message = f"✅ Félicitations ! Niveau {old_niveau} → {user.niveau_actuel}"
                
            else:
                # Échec : reste dans la même cohorte
                db.commit()
                message = f"❌ Échec - Vous restez dans la cohorte {user.cohorte_id} au niveau {user.niveau_actuel}"
            
            return message
        
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur update_user_after_exam: {e}")
            raise
        finally:
            db.close()
    
    def _find_cohort_for_level(self, niveau: int, db: Session) -> Cohorte:
        """Trouve une cohorte appropriée pour un niveau donné"""
        # Chercher une cohorte active au même niveau et pas pleine
        cohortes = db.query(Cohorte).filter(
            Cohorte.niveau_actuel == niveau,
            Cohorte.statut.in_(['active', 'en_formation'])
        ).all()
        
        for cohort in cohortes:
            membres_count = db.query(func.count(Utilisateur.user_id)).filter(
                Utilisateur.cohorte_id == cohort.id
            ).scalar()
            
            if membres_count < self.config['max_membres_par_cohorte']:
                return cohort
        
        # Aucune cohorte disponible, en créer une nouvelle
        cohort_id = self.create_cohort()
        new_cohort = db.query(Cohorte).filter(Cohorte.id == cohort_id).first()
        new_cohort.niveau_actuel = niveau
        db.commit()
        return new_cohort
    
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
