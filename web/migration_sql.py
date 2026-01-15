"""
Script de Migration SQL
Ajoute les nouvelles tables et colonnes pour le système de vote
À exécuter UNE SEULE FOIS dans PostgreSQL
"""

# ==================== OPTION 1 : Script Python ====================
# Copier ce code dans un fichier migration.py et l'exécuter

from db_connection import SessionLocal, engine
from sqlalchemy import text

def run_migration():
    """Exécute la migration complète"""
    db = SessionLocal()
    
    try:
        print("🔧 Début de la migration...")
        
        # 1. Ajouter les nouvelles colonnes à utilisateurs
        print("\n1️⃣ Ajout des colonnes à la table utilisateurs...")
        
        columns_to_add = [
            "ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS has_voted BOOLEAN NOT NULL DEFAULT FALSE;",
            "ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS current_exam_period VARCHAR(50);",
            "ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_points FLOAT NOT NULL DEFAULT 0.0;",
            "ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_level VARCHAR(20);"
        ]
        
        for sql in columns_to_add:
            try:
                db.execute(text(sql))
                db.commit()
                print(f"   ✅ {sql.split('ADD COLUMN')[1].split()[2]}")
            except Exception as e:
                print(f"   ⚠️ {e}")
                db.rollback()
        
        # 2. Créer la table votes
        print("\n2️⃣ Création de la table votes...")
        
        create_votes = """
        CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            voter_id BIGINT NOT NULL REFERENCES utilisateurs(user_id) ON DELETE CASCADE,
            voted_for_id BIGINT NOT NULL REFERENCES utilisateurs(user_id) ON DELETE CASCADE,
            exam_period_id VARCHAR(50) NOT NULL,
            date TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
        
        try:
            db.execute(text(create_votes))
            db.commit()
            print("   ✅ Table votes créée")
        except Exception as e:
            print(f"   ⚠️ {e}")
            db.rollback()
        
        # 3. Créer la table exam_periods
        print("\n3️⃣ Création de la table exam_periods...")
        
        create_exam_periods = """
        CREATE TABLE IF NOT EXISTS exam_periods (
            id VARCHAR(50) PRIMARY KEY,
            group_number INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            votes_closed BOOLEAN NOT NULL DEFAULT FALSE,
            bonuses_applied BOOLEAN NOT NULL DEFAULT FALSE
        );
        """
        
        try:
            db.execute(text(create_exam_periods))
            db.commit()
            print("   ✅ Table exam_periods créée")
        except Exception as e:
            print(f"   ⚠️ {e}")
            db.rollback()
        
        # 4. Créer les index pour optimiser les requêtes
        print("\n4️⃣ Création des index...")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_id);",
            "CREATE INDEX IF NOT EXISTS idx_votes_voted_for ON votes(voted_for_id);",
            "CREATE INDEX IF NOT EXISTS idx_votes_period ON votes(exam_period_id);",
            "CREATE INDEX IF NOT EXISTS idx_exam_periods_group ON exam_periods(group_number);",
            "CREATE INDEX IF NOT EXISTS idx_utilisateurs_voted ON utilisateurs(has_voted);",
        ]
        
        for idx_sql in indexes:
            try:
                db.execute(text(idx_sql))
                db.commit()
                print(f"   ✅ {idx_sql.split('idx_')[1].split()[0]}")
            except Exception as e:
                print(f"   ⚠️ {e}")
                db.rollback()
        
        print("\n" + "="*60)
        print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE : {e}")
        db.rollback()
    
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()


# ==================== OPTION 2 : SQL Direct ====================
# Copier ces commandes SQL et les exécuter directement dans PostgreSQL

"""
-- 1. Ajouter les colonnes à utilisateurs
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS has_voted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS current_exam_period VARCHAR(50);
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_points FLOAT NOT NULL DEFAULT 0.0;
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_level VARCHAR(20);

-- 2. Créer la table votes
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    voter_id BIGINT NOT NULL REFERENCES utilisateurs(user_id) ON DELETE CASCADE,
    voted_for_id BIGINT NOT NULL REFERENCES utilisateurs(user_id) ON DELETE CASCADE,
    exam_period_id VARCHAR(50) NOT NULL,
    date TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 3. Créer la table exam_periods
CREATE TABLE IF NOT EXISTS exam_periods (
    id VARCHAR(50) PRIMARY KEY,
    group_number INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    votes_closed BOOLEAN NOT NULL DEFAULT FALSE,
    bonuses_applied BOOLEAN NOT NULL DEFAULT FALSE
);

-- 4. Créer les index
CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_id);
CREATE INDEX IF NOT EXISTS idx_votes_voted_for ON votes(voted_for_id);
CREATE INDEX IF NOT EXISTS idx_votes_period ON votes(exam_period_id);
CREATE INDEX IF NOT EXISTS idx_exam_periods_group ON exam_periods(group_number);
CREATE INDEX IF NOT EXISTS idx_utilisateurs_voted ON utilisateurs(has_voted);
"""
