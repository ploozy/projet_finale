"""
Script de migration à exécuter UNE SEULE FOIS
"""
import os
from sqlalchemy import create_engine, text
from datetime import datetime

# Récupérer l'URL de la base de données
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Créer la connexion
engine = create_engine(DATABASE_URL)

# SQL de migration
migration_sql = """
-- Ajouter les colonnes pour le système de vote
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS has_voted BOOLEAN DEFAULT FALSE;
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS current_exam_period VARCHAR(50);
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_points FLOAT DEFAULT 0.0;
ALTER TABLE utilisateurs ADD COLUMN IF NOT EXISTS bonus_level VARCHAR(20);

-- Créer la table des votes
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    voter_id BIGINT NOT NULL,
    voted_for_id BIGINT NOT NULL,
    exam_period_id VARCHAR(50) NOT NULL,
    date TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (voter_id) REFERENCES utilisateurs(user_id) ON DELETE CASCADE,
    FOREIGN KEY (voted_for_id) REFERENCES utilisateurs(user_id) ON DELETE CASCADE
);

-- Créer la table des périodes d'examen
CREATE TABLE IF NOT EXISTS exam_periods (
    id VARCHAR(50) PRIMARY KEY,
    group_number INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    votes_closed BOOLEAN NOT NULL DEFAULT FALSE,
    bonuses_applied BOOLEAN NOT NULL DEFAULT FALSE
);

-- Créer les index
CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_id);
CREATE INDEX IF NOT EXISTS idx_votes_voted_for ON votes(voted_for_id);
CREATE INDEX IF NOT EXISTS idx_votes_period ON votes(exam_period_id);
CREATE INDEX IF NOT EXISTS idx_exam_periods_group ON exam_periods(group_number);
CREATE INDEX IF NOT EXISTS idx_utilisateurs_voted ON utilisateurs(has_voted);
CREATE INDEX IF NOT EXISTS idx_utilisateurs_period ON utilisateurs(current_exam_period);
"""

def run_migration():
    """Exécute la migration"""
    print("=" * 60)
    print("🔧 DÉBUT DE LA MIGRATION")
    print("=" * 60)
    
    try:
        with engine.connect() as conn:
            # Exécuter chaque commande SQL
            for statement in migration_sql.split(';'):
                statement = statement.strip()
                if statement:
                    print(f"\n📝 Exécution : {statement[:50]}...")
                    conn.execute(text(statement))
                    conn.commit()
                    print("✅ OK")
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
        print("=" * 60)
        
        # Vérification
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM votes"))
            print(f"\n✅ Table 'votes' accessible : {result.scalar()} entrées")
            
            result = conn.execute(text("SELECT COUNT(*) FROM exam_periods"))
            print(f"✅ Table 'exam_periods' accessible : {result.scalar()} entrées")
            
            result = conn.execute(text("SELECT has_voted, bonus_points FROM utilisateurs LIMIT 1"))
            print(f"✅ Colonnes ajoutées à 'utilisateurs' : OK")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERREUR LORS DE LA MIGRATION")
        print("=" * 60)
        print(f"Erreur : {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\n🎉 Tu peux maintenant déployer normalement !")
    else:
        print("\n⚠️ La migration a échoué. Vérifie les erreurs ci-dessus.")
