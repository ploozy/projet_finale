"""
Migration vers le nouveau système de groupes (sans cohortes JAN26-A)

ATTENTION : Cette migration modifie la structure de la base de données
Sauvegarde ta base avant d'exécuter ce script !

Usage: python migration_nouveau_systeme.py
"""
from db_connection import engine, SessionLocal
from models import Base, Utilisateur, WaitingList, RattrapageExam, ExamPeriod
from sqlalchemy import text
import sys


def run_migration():
    """Exécute la migration de la base de données"""
    print("\n" + "="*60)
    print("🔄 MIGRATION VERS LE NOUVEAU SYSTÈME")
    print("="*60 + "\n")

    try:
        # Demander confirmation
        print("⚠️  ATTENTION : Cette migration va modifier la structure de la base de données.")
        print("   Assurez-vous d'avoir fait une sauvegarde !\n")
        confirmation = input("Taper 'OUI' pour continuer: ")

        if confirmation != "OUI":
            print("❌ Migration annulée")
            sys.exit(0)

        db = SessionLocal()

        # 1. Ajouter les nouvelles colonnes à la table utilisateurs
        print("\n📝 Étape 1 : Ajout des nouvelles colonnes...")

        try:
            # Rendre cohorte_id nullable
            db.execute(text("ALTER TABLE utilisateurs ALTER COLUMN cohorte_id DROP NOT NULL"))
            print("  ✅ cohorte_id rendu nullable")
        except Exception as e:
            print(f"  ⚠️  cohorte_id déjà nullable ou erreur : {e}")

        try:
            # Ajouter is_alumni
            db.execute(text("ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS is_alumni BOOLEAN DEFAULT FALSE NOT NULL"))
            print("  ✅ Colonne is_alumni ajoutée")
        except Exception as e:
            print(f"  ⚠️  Colonne is_alumni déjà existante ou erreur : {e}")

        try:
            # Ajouter in_rattrapage
            db.execute(text("ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS in_rattrapage BOOLEAN DEFAULT FALSE NOT NULL"))
            print("  ✅ Colonne in_rattrapage ajoutée")
        except Exception as e:
            print(f"  ⚠️  Colonne in_rattrapage déjà existante ou erreur : {e}")

        db.commit()

        # 2. Ajouter les colonnes à exam_periods
        print("\n📝 Étape 2 : Mise à jour de la table exam_periods...")

        try:
            db.execute(text("ALTER TABLE exam_periods ADD COLUMN IF NOT EXISTS groupe VARCHAR(10)"))
            print("  ✅ Colonne groupe ajoutée à exam_periods")
        except Exception as e:
            print(f"  ⚠️  Colonne groupe déjà existante ou erreur : {e}")

        try:
            db.execute(text("ALTER TABLE exam_periods ADD COLUMN IF NOT EXISTS is_rattrapage BOOLEAN DEFAULT FALSE NOT NULL"))
            print("  ✅ Colonne is_rattrapage ajoutée à exam_periods")
        except Exception as e:
            print(f"  ⚠️  Colonne is_rattrapage déjà existante ou erreur : {e}")

        db.commit()

        # 3. Créer les nouvelles tables
        print("\n📝 Étape 3 : Création des nouvelles tables...")

        # Créer toutes les tables (celles qui n'existent pas seront créées)
        Base.metadata.create_all(engine)
        print("  ✅ Tables waiting_lists et rattrapage_exams créées")

        # 4. Migrer les données existantes (optionnel)
        print("\n📝 Étape 4 : Migration des données existantes...")

        # Définir cohorte_id à NULL pour tous les utilisateurs (nouveau système sans cohortes)
        # db.execute(text("UPDATE utilisateurs SET cohorte_id = NULL"))
        # print("  ✅ cohorte_id mis à NULL pour tous les utilisateurs")
        print("  ⚠️  Migration des données ignorée (à faire manuellement si besoin)")

        db.commit()

        print("\n" + "="*60)
        print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
        print("="*60 + "\n")

        print("📋 Résumé des changements :")
        print("  • Colonnes ajoutées à 'utilisateurs' : is_alumni, in_rattrapage")
        print("  • cohorte_id rendu nullable dans 'utilisateurs'")
        print("  • Colonnes ajoutées à 'exam_periods' : groupe, is_rattrapage")
        print("  • Nouvelles tables créées : waiting_lists, rattrapage_exams")
        print("\n💡 Le système de cohortes (JAN26-A) n'est plus utilisé.")
        print("   Les groupes sont maintenant gérés directement (X-Y).\n")

        db.close()

    except Exception as e:
        print(f"\n❌ Erreur lors de la migration : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
