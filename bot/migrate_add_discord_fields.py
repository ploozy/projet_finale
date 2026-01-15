"""
Script de migration pour ajouter les colonnes Discord aux cohortes existantes
À exécuter UNE SEULE FOIS si vous avez déjà une base de données en production
"""
from sqlalchemy import text
from db_connection import engine, test_connection
import sys


def add_discord_columns():
    """Ajoute les colonnes guild_id, role_id, channel_id à la table cohortes"""
    
    print("=" * 60)
    print("🔧 MIGRATION : Ajout des colonnes Discord")
    print("=" * 60)
    
    # Test de connexion
    print("\n1️⃣ Test de connexion...")
    if not test_connection():
        print("❌ Impossible de se connecter à PostgreSQL")
        sys.exit(1)
    
    print("\n2️⃣ Ajout des colonnes...")
    
    queries = [
        """
        ALTER TABLE cohortes 
        ADD COLUMN IF NOT EXISTS guild_id BIGINT NULL;
        """,
        """
        ALTER TABLE cohortes 
        ADD COLUMN IF NOT EXISTS role_id BIGINT NULL;
        """,
        """
        ALTER TABLE cohortes 
        ADD COLUMN IF NOT EXISTS channel_id BIGINT NULL;
        """
    ]
    
    with engine.connect() as conn:
        for query in queries:
            try:
                conn.execute(text(query))
                conn.commit()
                print("  ✅ Colonne ajoutée")
            except Exception as e:
                print(f"  ⚠️ Colonne déjà existante ou erreur : {e}")
    
    print("\n3️⃣ Création des index...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cohortes_guild ON cohortes(guild_id);",
        "CREATE INDEX IF NOT EXISTS idx_cohortes_role ON cohortes(role_id);",
        "CREATE INDEX IF NOT EXISTS idx_cohortes_channel ON cohortes(channel_id);"
    ]
    
    with engine.connect() as conn:
        for idx_query in indexes:
            try:
                conn.execute(text(idx_query))
                conn.commit()
                print("  ✅ Index créé")
            except Exception as e:
                print(f"  ⚠️ Index déjà existant : {e}")
    
    print("\n" + "=" * 60)
    print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
    print("=" * 60)
    print("\nLes cohortes existantes peuvent maintenant être liées à Discord.")
    print("Exécutez /sync_roles sur Discord pour créer les rôles et salons.")


if __name__ == "__main__":
    response = input("⚠️ Cette migration va modifier la base de données. Continuer ? (oui/non) : ")
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        add_discord_columns()
    else:
        print("❌ Migration annulée")
