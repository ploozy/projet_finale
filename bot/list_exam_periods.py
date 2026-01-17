"""
Script pour lister toutes les périodes d'examen
Exécute: python list_exam_periods.py
"""
from datetime import datetime
from db_connection import SessionLocal
from models import ExamPeriod

db = SessionLocal()

try:
    print("\n📅 PÉRIODES D'EXAMEN PROGRAMMÉES")
    print("=" * 80)

    periods = db.query(ExamPeriod).order_by(ExamPeriod.start_time).all()

    if not periods:
        print("❌ Aucune période d'examen créée")
    else:
        for period in periods:
            status = "✅ Terminée" if period.bonuses_applied else "⏳ En cours/À venir"

            print(f"\n🆔 {period.id}")
            print(f"   📊 Groupe: {period.group_number}")
            print(f"   🗳️  Votes: {period.vote_start_time.strftime('%d/%m/%Y %H:%M')}")
            print(f"   🟢 Début: {period.start_time.strftime('%d/%m/%Y %H:%M')}")
            print(f"   🔴 Fin:   {period.end_time.strftime('%d/%m/%Y %H:%M')}")
            print(f"   {status}")

        print("\n" + "=" * 80)
        print(f"Total: {len(periods)} période(s)")

except Exception as e:
    print(f"❌ Erreur: {e}")

finally:
    db.close()
