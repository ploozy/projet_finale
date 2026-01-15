"""
Script d'initialisation de la base de données PostgreSQL
À exécuter UNE SEULE FOIS au premier déploiement
"""
import os
import sys
from db_connection import init_db, test_connection, engine
from sqlalchemy import text

def create_indexes():
    """Crée les index pour optimiser les requêtes"""
    print("📊 Création des index...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_utilisateurs_cohorte ON utilisateurs(cohorte_id);",
        "CREATE INDEX IF NOT EXISTS idx_calendrier_cohorte ON calendrier_examens(cohorte_id);",
        "CREATE INDEX IF NOT EXISTS idx_reviews_next ON reviews(next_review);",
        "CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_exam_results_user ON exam_results(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_exam_results_notified ON exam_results(notified);",
    ]
    
    with engine.connect() as conn:
        for idx_query in indexes:
            try:
                conn.execute(text(idx_query))
                conn.commit()
            except Exception as e:
                print(f"⚠️ Index déjà existant ou erreur : {e}")
    
    print("✅ Index créés")

def main():
    """Fonction principale d'initialisation"""
    print("=" * 60)
    print("🚀 INITIALISATION DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    # Vérifier que DATABASE_URL est définie
    if not os.getenv('DATABASE_URL'):
        print("❌ ERREUR : DATABASE_URL n'est pas définie")
        print("   Ajoutez-la dans Render Dashboard > Environment Variables")
        sys.exit(1)
    
    # Tester la connexion
    print("\n1️⃣ Test de connexion...")
    if not test_connection():
        print("❌ Impossible de se connecter à PostgreSQL")
        sys.exit(1)
    
    # Créer les tables
    print("\n2️⃣ Création des tables...")
    try:
        init_db()
    except Exception as e:
        print(f"❌ Erreur lors de la création des tables : {e}")
        sys.exit(1)
    
    # Créer les index
    print("\n3️⃣ Création des index...")
    try:
        create_indexes()
    except Exception as e:
        print(f"⚠️ Avertissement lors de la création des index : {e}")
    
    print("\n" + "=" * 60)
    print("✅ INITIALISATION TERMINÉE AVEC SUCCÈS")
    print("=" * 60)
    print("\nLa base de données est prête à être utilisée !")
    print("Vous pouvez maintenant démarrer votre application.")

if __name__ == "__main__":
    main()
