"""
Script de migration : Ajout de la colonne 'groupe' à la table utilisateurs
Execute ce script UNE SEULE FOIS pour mettre à jour la base de données
"""

from db_connection import SessionLocal, engine
from sqlalchemy import text

def add_groupe_column():
    """Ajoute la colonne 'groupe' à la table utilisateurs"""
    db = SessionLocal()
    
    try:
        print("🔧 Ajout de la colonne 'groupe' à la table utilisateurs...")
        
        # Vérifier si la colonne existe déjà
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='utilisateurs' AND column_name='groupe'
        """)
        
        result = db.execute(check_query).fetchone()
        
        if result:
            print("✅ La colonne 'groupe' existe déjà")
            return
        
        # Ajouter la colonne
        alter_query = text("""
            ALTER TABLE utilisateurs 
            ADD COLUMN groupe VARCHAR(10) DEFAULT '1-A'
        """)
        
        db.execute(alter_query)
        db.commit()
        
        print("✅ Colonne 'groupe' ajoutée avec succès !")
        
        # Mettre à jour les utilisateurs existants
        print("🔄 Mise à jour des utilisateurs existants...")
        
        update_query = text("""
            UPDATE utilisateurs 
            SET groupe = CONCAT(niveau_actuel::text, '-A')
            WHERE groupe IS NULL OR groupe = ''
        """)
        
        db.execute(update_query)
        db.commit()
        
        print("✅ Utilisateurs existants mis à jour !")
        
        # Afficher le résultat
        count_query = text("SELECT COUNT(*) FROM utilisateurs")
        count = db.execute(count_query).scalar()
        
        print(f"📊 Total utilisateurs : {count}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors de la migration : {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("MIGRATION : Ajout colonne 'groupe'")
    print("=" * 50)
    
    add_groupe_column()
    
    print("\n✅ Migration terminée avec succès !")
    print("=" * 50)
