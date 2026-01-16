"""
Script de migration: Ajoute vote_start_time aux ExamPeriod existants
À exécuter une seule fois après déploiement
"""
from sqlalchemy import text, inspect
from datetime import timedelta
from db_connection import SessionLocal, engine
from models import ExamPeriod

def migrate():
    """Ajoute la colonne vote_start_time et calcule les valeurs pour les périodes existantes"""
    db = SessionLocal()

    try:
        print("🔧 Migration: Ajout de vote_start_time aux ExamPeriod")
        print("=" * 60)

        # 1. Vérifier si la colonne existe déjà
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('exam_periods')]

        if 'vote_start_time' in columns:
            print("✅ La colonne vote_start_time existe déjà")
            return

        # 2. Ajouter la colonne (nullable temporairement)
        print("\n📝 Ajout de la colonne vote_start_time...")
        db.execute(text("""
            ALTER TABLE exam_periods
            ADD COLUMN vote_start_time TIMESTAMP NULL
        """))
        db.commit()
        print("✅ Colonne ajoutée")

        # 3. Calculer vote_start_time pour les périodes existantes
        print("\n🔄 Calcul des vote_start_time pour les périodes existantes...")
        periods = db.query(ExamPeriod).all()

        if not periods:
            print("ℹ️  Aucune période d'examen existante")
        else:
            for period in periods:
                # vote_start_time = start_time - 24h
                period.vote_start_time = period.start_time - timedelta(days=1)
                print(f"  • {period.id}: {period.vote_start_time.strftime('%Y-%m-%d %H:%M')}")

            db.commit()
            print(f"✅ {len(periods)} période(s) mise(s) à jour")

        # 4. Rendre la colonne NOT NULL
        print("\n🔒 Mise en place de la contrainte NOT NULL...")
        db.execute(text("""
            ALTER TABLE exam_periods
            ALTER COLUMN vote_start_time SET NOT NULL
        """))
        db.commit()
        print("✅ Contrainte appliquée")

        print("\n" + "=" * 60)
        print("✅ Migration terminée avec succès!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erreur lors de la migration: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
