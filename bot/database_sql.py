"""
Gestion des révisions espacées (Spaced Repetition) avec PostgreSQL
Remplace l'ancien database.py basé sur JSON
"""
from sqlalchemy.orm import Session
from datetime import datetime
from models import Review
from db_connection import SessionLocal


class ReviewDatabaseSQL:
    """Gestion du stockage persistant des révisions avec PostgreSQL"""
    
    def save_review(self, review_data: dict):
        """
        Sauvegarde ou met à jour une révision
        
        Args:
            review_data (dict): {
                'user_id': int,
                'question_id': int,
                'next_review': datetime,
                'interval': float,
                'repetitions': int,
                'easiness_factor': float
            }
        """
        db = SessionLocal()
        try:
            # Vérifier si la révision existe déjà
            existing = db.query(Review).filter(
                Review.user_id == review_data['user_id'],
                Review.question_id == review_data['question_id']
            ).first()
            
            if existing:
                # Mise à jour
                existing.next_review = review_data['next_review']
                existing.interval_days = review_data['interval']
                existing.repetitions = review_data['repetitions']
                existing.easiness_factor = review_data['easiness_factor']
            else:
                # Création
                new_review = Review(
                    user_id=review_data['user_id'],
                    question_id=review_data['question_id'],
                    next_review=review_data['next_review'],
                    interval_days=review_data['interval'],
                    repetitions=review_data['repetitions'],
                    easiness_factor=review_data['easiness_factor']
                )
                db.add(new_review)
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur save_review: {e}")
            raise
        finally:
            db.close()
    
    def get_review(self, user_id: int, question_id: int) -> dict:
        """
        Récupère une révision spécifique
        
        Returns:
            dict ou None si la révision n'existe pas
        """
        db = SessionLocal()
        try:
            review = db.query(Review).filter(
                Review.user_id == user_id,
                Review.question_id == question_id
            ).first()
            
            if not review:
                return None
            
            return {
                'user_id': review.user_id,
                'question_id': review.question_id,
                'next_review': review.next_review,
                'interval': review.interval_days,
                'repetitions': review.repetitions,
                'easiness_factor': review.easiness_factor
            }
        finally:
            db.close()
    
    def get_user_reviews(self, user_id: int) -> list:
        """Récupère toutes les révisions d'un utilisateur"""
        db = SessionLocal()
        try:
            reviews = db.query(Review).filter(
                Review.user_id == user_id
            ).all()
            
            return [{
                'user_id': r.user_id,
                'question_id': r.question_id,
                'next_review': r.next_review,
                'interval': r.interval_days,
                'repetitions': r.repetitions,
                'easiness_factor': r.easiness_factor
            } for r in reviews]
        finally:
            db.close()
    
    def get_all_reviews(self) -> list:
        """Récupère toutes les révisions"""
        db = SessionLocal()
        try:
            reviews = db.query(Review).all()
            
            return [{
                'user_id': r.user_id,
                'question_id': r.question_id,
                'next_review': r.next_review,
                'interval': r.interval_days,
                'repetitions': r.repetitions,
                'easiness_factor': r.easiness_factor
            } for r in reviews]
        finally:
            db.close()
    
    def is_review_due(self, review_data: dict) -> bool:
        """Vérifie si une révision est due"""
        return datetime.now() >= review_data['next_review']
    
    def delete_review(self, user_id: int, question_id: int):
        """Supprime une révision (optionnel)"""
        db = SessionLocal()
        try:
            review = db.query(Review).filter(
                Review.user_id == user_id,
                Review.question_id == question_id
            ).first()
            
            if review:
                db.delete(review)
                db.commit()
                print(f"✅ Révision supprimée : user={user_id}, question={question_id}")
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur delete_review: {e}")
            raise
        finally:
            db.close()
    
    def get_due_reviews(self) -> list:
        """
        Récupère toutes les révisions dues (next_review <= maintenant)
        Utile pour le scheduler
        """
        db = SessionLocal()
        try:
            now = datetime.now()
            reviews = db.query(Review).filter(
                Review.next_review <= now
            ).all()
            
            return [{
                'user_id': r.user_id,
                'question_id': r.question_id,
                'next_review': r.next_review,
                'interval': r.interval_days,
                'repetitions': r.repetitions,
                'easiness_factor': r.easiness_factor
            } for r in reviews]
        finally:
            db.close()
