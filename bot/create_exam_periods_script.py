"""
Script pour créer plusieurs périodes d'examen en une fois
Exécute ce fichier avec: python create_exam_periods_script.py
"""
from datetime import datetime, timedelta
from db_connection import SessionLocal
from models import ExamPeriod

# ==================== CONFIGURE ICI ====================

# Liste des périodes à créer
# Format: (groupe, date_debut)
EXAM_PERIODS = [
    (1, "2026-01-20 14:00"),  # Groupe 1 - 20 janvier à 14h
    (2, "2026-01-27 14:00"),  # Groupe 2 - 27 janvier à 14h
    (3, "2026-02-03 14:00"),  # Groupe 3 - 3 février à 14h
    (4, "2026-02-10 14:00"),  # Groupe 4 - 10 février à 14h
    (5, "2026-02-17 14:00"),  # Groupe 5 - 17 février à 14h
]

# ==================== NE TOUCHE PAS EN DESSOUS ====================

def create_exam_periods():
    """Crée les périodes d'examen"""
    db = SessionLocal()

    try:
        print("🔧 Création des périodes d'examen...")
        print("=" * 60)

        for group_number, start_time_str in EXAM_PERIODS:
            # Parser la date
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")

            # Calculer fin (6h après)
            end_time = start_time + timedelta(hours=6)

            # Calculer ouverture votes (24h avant)
            vote_start_time = start_time - timedelta(days=1)

            # Générer ID unique
            period_id = f"{start_time.strftime('%Y-%m-%d_%H%M')}_group{group_number}"

            # Vérifier si existe déjà
            existing = db.query(ExamPeriod).filter(
                ExamPeriod.id == period_id
            ).first()

            if existing:
                print(f"⚠️  Groupe {group_number} - Période déjà existante, ignorée")
                continue

            # Créer la période
            period = ExamPeriod(
                id=period_id,
                group_number=group_number,
                vote_start_time=vote_start_time,
                start_time=start_time,
                end_time=end_time,
                votes_closed=False,
                bonuses_applied=False
            )

            db.add(period)

            print(f"\n✅ Groupe {group_number}:")
            print(f"   🗳️  Votes ouverts: {vote_start_time.strftime('%d/%m/%Y à %H:%M')}")
            print(f"   🟢 Début examen: {start_time.strftime('%d/%m/%Y à %H:%M')}")
            print(f"   🔴 Fin examen:   {end_time.strftime('%d/%m/%Y à %H:%M')}")

        # Sauvegarder tout
        db.commit()

        print("\n" + "=" * 60)
        print("✅ Toutes les périodes ont été créées!")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    create_exam_periods()
