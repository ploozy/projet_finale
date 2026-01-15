"""
Script de migration : Ajout de la colonne 'groupe' à la table utilisateurs
"""

from db_connection import SessionLocal
from sqlalchemy import text

def add_groupe_column():
    """Ajoute la colonne 'groupe' si elle n'existe pas"""
    db = SessionLocal()
    
    try:
        # Vérifier si la colonne existe
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='utilisateurs' AND column_name='groupe'
        """)
        
        result = db.execute(check_query).fetchone()
        
        if result:
            print("✅ Colonne 'groupe' existe déjà")
            return
        
        print("🔧 Ajout de la colonne 'groupe'...")
        
        # Ajouter la colonne
        alter_query = text("""
            ALTER TABLE utilisateurs 
            ADD COLUMN groupe VARCHAR(10) DEFAULT '1-A'
        """)
        
        db.execute(alter_query)
        db.commit()
        
        print("✅ Colonne 'groupe' ajoutée !")
        
        # Mettre à jour les utilisateurs existants
        update_query = text("""
            UPDATE utilisateurs 
            SET groupe = CONCAT(niveau_actuel::text, '-A')
            WHERE groupe IS NULL OR groupe = ''
        """)
        
        db.execute(update_query)
        db.commit()
        
        print("✅ Utilisateurs existants mis à jour !")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur migration : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_groupe_column()
