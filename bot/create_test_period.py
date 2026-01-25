"""
Script pour créer une période d'examen de TEST
À exécuter une seule fois pour permettre les votes en mode test
"""

from datetime import datetime, timedelta
from db_connection import SessionLocal
from models import ExamPeriod
from sqlalchemy import text

print("🔧 Création de la période d'examen 'test'...")

db = SessionLocal()

try:
    # Supprimer l'ancienne période "test" si elle existe (avec ses votes)
    print("  - Suppression des anciens votes 'test'...")
    db.execute(text("DELETE FROM votes WHERE exam_period_id = 'test'"))

    print("  - Suppression de l'ancienne période 'test'...")
    db.execute(text("DELETE FROM exam_periods WHERE id = 'test'"))

    db.commit()

    # Créer la nouvelle période "test"
    print("  - Création de la nouvelle période 'test'...")
    now = datetime.utcnow()

    test_period = ExamPeriod(
        id="test",
        group_number=1,
        start_time=now,
        end_time=now + timedelta(days=365),  # Valide 1 an
        vote_start_time=now,
        votes_closed=False
    )

    db.add(test_period)
    db.commit()

    print("✅ Période d'examen 'test' créée avec succès!")
    print(f"   - Valide jusqu'au: {test_period.end_time}")
    print(f"   - Groupe: {test_period.group_number}")
    print("\n🎯 Tu peux maintenant utiliser /vote sur Discord!")

except Exception as e:
    print(f"❌ Erreur: {e}")
    db.rollback()

finally:
    db.close()
