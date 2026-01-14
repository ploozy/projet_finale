"""
Script de migration des données JSON vers PostgreSQL
À exécuter après init_db.py si vous avez déjà des données
"""
import json
import os
from datetime import datetime
from db_connection import SessionLocal
from models import Cohorte, Utilisateur, CalendrierExamen, HistoriqueCohorte, Review, ExamResult


def migrate_cohortes(json_file='cohortes.json'):
    """Migre les données de cohortes.json vers PostgreSQL"""
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} introuvable, migration ignorée")
        return
    
    print(f"\n📦 Migration de {json_file}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    db = SessionLocal()
    try:
        # Migrer les cohortes
        print("  → Migration des cohortes...")
        for cohort_data in data.get('cohortes', []):
            existing = db.query(Cohorte).filter(Cohorte.id == cohort_data['id']).first()
            if existing:
                print(f"    ⚠️ Cohorte {cohort_data['id']} existe déjà, ignorée")
                continue
            
            cohort = Cohorte(
                id=cohort_data['id'],
                date_creation=datetime.fromisoformat(cohort_data['date_creation']),
                date_premier_examen=datetime.fromisoformat(cohort_data['date_premier_examen']),
                date_fermeture=datetime.fromisoformat(cohort_data['date_fermeture']) if cohort_data.get('date_fermeture') else None,
                niveau_actuel=cohort_data['niveau_actuel'],
                statut=cohort_data['statut']
            )
            db.add(cohort)
            
            # Migrer le calendrier
            for cal_data in cohort_data.get('calendrier_examens', []):
                cal = CalendrierExamen(
                    cohorte_id=cohort_data['id'],
                    niveau=cal_data['niveau'],
                    exam_id=cal_data['exam_id'],
                    date_examen=datetime.fromisoformat(cal_data['date_examen'])
                )
                db.add(cal)
        
        db.commit()
        print(f"  ✅ {len(data.get('cohortes', []))} cohortes migrées")
        
        # Migrer les utilisateurs
        print("  → Migration des utilisateurs...")
        for user_data in data.get('utilisateurs', []):
            existing = db.query(Utilisateur).filter(Utilisateur.user_id == user_data['user_id']).first()
            if existing:
                print(f"    ⚠️ Utilisateur {user_data['user_id']} existe déjà, ignoré")
                continue
            
            user = Utilisateur(
                user_id=user_data['user_id'],
                username=user_data['username'],
                cohorte_id=user_data['cohorte_id'],
                niveau_actuel=user_data['niveau_actuel'],
                examens_reussis=user_data.get('examens_reussis', 0),
                date_inscription=datetime.fromisoformat(user_data['date_inscription'])
            )
            db.add(user)
            
            # Migrer l'historique des cohortes
            for cohort_id in user_data.get('historique_cohortes', []):
                hist = HistoriqueCohorte(
                    user_id=user_data['user_id'],
                    cohorte_id=cohort_id,
                    date_ajout=datetime.fromisoformat(user_data['date_inscription'])
                )
                db.add(hist)
        
        db.commit()
        print(f"  ✅ {len(data.get('utilisateurs', []))} utilisateurs migrés")
    
    except Exception as e:
        db.rollback()
        print(f"  ❌ Erreur lors de la migration : {e}")
        raise
    finally:
        db.close()


def migrate_reviews(json_file='reviews.json'):
    """Migre les données de reviews.json vers PostgreSQL"""
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} introuvable, migration ignorée")
        return
    
    print(f"\n📦 Migration de {json_file}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    db = SessionLocal()
    try:
        for review_data in data.get('reviews', []):
            existing = db.query(Review).filter(
                Review.user_id == review_data['user_id'],
                Review.question_id == review_data['question_id']
            ).first()
            
            if existing:
                print(f"  ⚠️ Review user={review_data['user_id']}, q={review_data['question_id']} existe, mise à jour")
                existing.next_review = datetime.fromisoformat(review_data['next_review'])
                existing.interval_days = review_data['interval']
                existing.repetitions = review_data['repetitions']
                existing.easiness_factor = review_data['easiness_factor']
            else:
                review = Review(
                    user_id=review_data['user_id'],
                    question_id=review_data['question_id'],
                    next_review=datetime.fromisoformat(review_data['next_review']),
                    interval_days=review_data['interval'],
                    repetitions=review_data['repetitions'],
                    easiness_factor=review_data['easiness_factor']
                )
                db.add(review)
        
        db.commit()
        print(f"  ✅ {len(data.get('reviews', []))} reviews migrées")
    
    except Exception as e:
        db.rollback()
        print(f"  ❌ Erreur lors de la migration : {e}")
        raise
    finally:
        db.close()


def migrate_exam_results(json_file='data/exam_results.json'):
    """Migre les résultats d'examens vers PostgreSQL"""
    if not os.path.exists(json_file):
        print(f"⚠️ Fichier {json_file} introuvable, migration ignorée")
        return
    
    print(f"\n📦 Migration de {json_file}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    db = SessionLocal()
    try:
        for result_data in data.get('exam_results', []):
            result = ExamResult(
                user_id=result_data['user_id'],
                exam_id=result_data['exam_id'],
                exam_title=result_data['exam_title'],
                score=result_data['score'],
                total=result_data['total'],
                percentage=result_data['percentage'],
                passed=result_data['passed'],
                passing_score=result_data['passing_score'],
                date=datetime.fromisoformat(result_data['date']),
                notified=result_data.get('notified', False),
                results=result_data.get('results')
            )
            db.add(result)
        
        db.commit()
        print(f"  ✅ {len(data.get('exam_results', []))} résultats d'examens migrés")
    
    except Exception as e:
        db.rollback()
        print(f"  ❌ Erreur lors de la migration : {e}")
        raise
    finally:
        db.close()


def main():
    """Fonction principale de migration"""
    print("=" * 60)
    print("📦 MIGRATION DES DONNÉES JSON → POSTGRESQL")
    print("=" * 60)
    print("\n⚠️ ATTENTION : Ce script ne doit être exécuté qu'UNE SEULE FOIS")
    print("             après avoir initialisé la base avec init_db.py\n")
    
    response = input("Voulez-vous continuer ? (oui/non) : ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("❌ Migration annulée")
        return
    
    try:
        # Migration des cohortes et utilisateurs
        migrate_cohortes('cohortes.json')
        
        # Migration des reviews
        migrate_reviews('reviews.json')
        
        # Migration des résultats d'examens
        migrate_exam_results('data/exam_results.json')
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
        print("=" * 60)
        print("\nToutes vos données ont été transférées vers PostgreSQL !")
        print("Vous pouvez maintenant supprimer les fichiers JSON si vous le souhaitez.")
    
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERREUR LORS DE LA MIGRATION")
        print("=" * 60)
        print(f"\nErreur : {e}")
        print("\nVeuillez corriger l'erreur et relancer le script.")


if __name__ == "__main__":
    main()
