"""
Gestion des résultats d'examens avec PostgreSQL
Utilisé par le site web pour enregistrer et récupérer les résultats
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from models import ExamResult
from db_connection import SessionLocal


class ExamResultDatabaseSQL:
    """Gestion des résultats d'examens pour le web"""
    
    def save_exam_result(self, exam_result: dict, max_per_user: int = 10):
        """
        Sauvegarde un résultat d'examen et limite le nombre par utilisateur
        
        Args:
            exam_result (dict): {
                'user_id': int,
                'exam_id': int,
                'exam_title': str,
                'score': int,
                'total': int,
                'percentage': float,
                'passed': bool,
                'passing_score': int,
                'date': datetime (optionnel),
                'results': list (optionnel - détails des réponses)
            }
            max_per_user (int): Nombre maximum de résultats conservés par utilisateur
        """
        db = SessionLocal()
        try:
            # Créer le nouveau résultat
            new_result = ExamResult(
                user_id=exam_result['user_id'],
                exam_id=exam_result['exam_id'],
                exam_title=exam_result['exam_title'],
                score=exam_result['score'],
                total=exam_result['total'],
                percentage=exam_result['percentage'],
                passed=exam_result['passed'],
                passing_score=exam_result['passing_score'],
                date=exam_result.get('date', datetime.now()),
                notified=False,
                results=exam_result.get('results')
            )
            db.add(new_result)
            
            # Limiter le nombre de résultats par utilisateur
            user_results = db.query(ExamResult).filter(
                ExamResult.user_id == exam_result['user_id']
            ).order_by(ExamResult.date.desc()).all()
            
            if len(user_results) >= max_per_user:
                # Supprimer les plus anciens
                for old_result in user_results[max_per_user - 1:]:
                    db.delete(old_result)
            
            db.commit()
            print(f"✅ Résultat enregistré : user={exam_result['user_id']}, score={exam_result['score']}/{exam_result['total']}")
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur save_exam_result: {e}")
            raise
        finally:
            db.close()
    
    def get_user_exam_results(self, user_id: int) -> list:
        """Récupère tous les résultats d'un utilisateur"""
        db = SessionLocal()
        try:
            results = db.query(ExamResult).filter(
                ExamResult.user_id == user_id
            ).order_by(ExamResult.date.desc()).all()
            
            return [{
                'id': r.id,
                'user_id': r.user_id,
                'exam_id': r.exam_id,
                'exam_title': r.exam_title,
                'score': r.score,
                'total': r.total,
                'percentage': r.percentage,
                'passed': r.passed,
                'passing_score': r.passing_score,
                'date': r.date.isoformat(),
                'notified': r.notified,
                'results': r.results
            } for r in results]
        finally:
            db.close()
    
    def get_latest_exam_results(self, limit: int = 10) -> list:
        """Récupère les derniers résultats (tous utilisateurs)"""
        db = SessionLocal()
        try:
            results = db.query(ExamResult).order_by(
                ExamResult.date.desc()
            ).limit(limit).all()
            
            return [{
                'id': r.id,
                'user_id': r.user_id,
                'exam_id': r.exam_id,
                'exam_title': r.exam_title,
                'score': r.score,
                'total': r.total,
                'percentage': r.percentage,
                'passed': r.passed,
                'date': r.date.isoformat(),
                'notified': r.notified
            } for r in results]
        finally:
            db.close()
    
    def get_unnotified_results(self, limit: int = 50) -> list:
        """
        Récupère uniquement les résultats non notifiés
        Utilisé par le bot Discord pour envoyer les notifications
        """
        db = SessionLocal()
        try:
            results = db.query(ExamResult).filter(
                ExamResult.notified == False
            ).order_by(ExamResult.date.desc()).limit(limit).all()
            
            return [{
                'id': r.id,
                'user_id': r.user_id,
                'exam_id': r.exam_id,
                'exam_title': r.exam_title,
                'score': r.score,
                'total': r.total,
                'percentage': r.percentage,
                'passed': r.passed,
                'passing_score': r.passing_score,
                'date': r.date.isoformat(),
                'results': r.results
            } for r in results]
        finally:
            db.close()
    
    def mark_as_notified(self, user_id: int, exam_id: int, date: str):
        """
        Marque un résultat comme notifié
        
        Args:
            user_id (int): ID de l'utilisateur
            exam_id (int): ID de l'examen
            date (str): Date au format ISO
        """
        db = SessionLocal()
        try:
            # Convertir la date string en datetime
            date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
            
            result = db.query(ExamResult).filter(
                and_(
                    ExamResult.user_id == user_id,
                    ExamResult.exam_id == exam_id,
                    ExamResult.date == date_obj
                )
            ).first()
            
            if result:
                result.notified = True
                db.commit()
                print(f"✅ Résultat marqué comme notifié : user={user_id}, exam={exam_id}")
            else:
                print(f"⚠️ Résultat non trouvé pour notification : user={user_id}, exam={exam_id}")
        except Exception as e:
            db.rollback()
            print(f"❌ Erreur mark_as_notified: {e}")
            raise
        finally:
            db.close()
    
    def get_exam_statistics(self, exam_id: int) -> dict:
        """
        Récupère les statistiques d'un examen
        
        Returns:
            dict: {
                'total_attempts': int,
                'passed_count': int,
                'failed_count': int,
                'average_score': float,
                'pass_rate': float
            }
        """
        db = SessionLocal()
        try:
            results = db.query(ExamResult).filter(
                ExamResult.exam_id == exam_id
            ).all()
            
            if not results:
                return {
                    'total_attempts': 0,
                    'passed_count': 0,
                    'failed_count': 0,
                    'average_score': 0,
                    'pass_rate': 0
                }
            
            total_attempts = len(results)
            passed_count = sum(1 for r in results if r.passed)
            failed_count = total_attempts - passed_count
            average_score = sum(r.percentage for r in results) / total_attempts
            pass_rate = (passed_count / total_attempts) * 100
            
            return {
                'total_attempts': total_attempts,
                'passed_count': passed_count,
                'failed_count': failed_count,
                'average_score': round(average_score, 2),
                'pass_rate': round(pass_rate, 2)
            }
        finally:
            db.close()
    
    def get_user_statistics(self, user_id: int) -> dict:
        """
        Récupère les statistiques d'un utilisateur
        
        Returns:
            dict: {
                'total_exams': int,
                'passed_exams': int,
                'failed_exams': int,
                'average_score': float,
                'best_score': float,
                'recent_exams': list
            }
        """
        db = SessionLocal()
        try:
            results = db.query(ExamResult).filter(
                ExamResult.user_id == user_id
            ).order_by(ExamResult.date.desc()).all()
            
            if not results:
                return {
                    'total_exams': 0,
                    'passed_exams': 0,
                    'failed_exams': 0,
                    'average_score': 0,
                    'best_score': 0,
                    'recent_exams': []
                }
            
            total_exams = len(results)
            passed_exams = sum(1 for r in results if r.passed)
            failed_exams = total_exams - passed_exams
            average_score = sum(r.percentage for r in results) / total_exams
            best_score = max(r.percentage for r in results)
            
            recent_exams = [{
                'exam_title': r.exam_title,
                'score': r.score,
                'total': r.total,
                'percentage': r.percentage,
                'passed': r.passed,
                'date': r.date.isoformat()
            } for r in results[:5]]  # 5 derniers examens
            
            return {
                'total_exams': total_exams,
                'passed_exams': passed_exams,
                'failed_exams': failed_exams,
                'average_score': round(average_score, 2),
                'best_score': round(best_score, 2),
                'recent_exams': recent_exams
            }
        finally:
            db.close()
