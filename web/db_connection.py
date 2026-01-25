"""
Connexion à la base de données PostgreSQL
Fichier partagé entre Bot Discord et Site Web
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Charger le fichier .env depuis la RACINE du projet
# Cherche .env dans le dossier parent (racine)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Récupération de l'URL depuis les variables d'environnement
DATABASE_URL = os.getenv('DATABASE_URL')

print(f"🔍 DATABASE_URL trouvée: {DATABASE_URL is not None}")
if DATABASE_URL:
    print(f"🔍 Début de l'URL: {DATABASE_URL[:50]}...")

if not DATABASE_URL:
    raise ValueError(
        "❌ DATABASE_URL n'est pas définie dans les variables d'environnement. "
        "Ajoutez-la dans Render Dashboard > Service > Environment > Add Environment Variable"
    )

# Fix pour Render : postgres:// → postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    print("🔧 URL corrigée de postgres:// vers postgresql://")

# Configuration du moteur SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,              # Nombre de connexions dans le pool
    max_overflow=10,          # Connexions supplémentaires max
    pool_pre_ping=True,       # Vérifie la connexion avant utilisation
    pool_recycle=3600,        # Recycle les connexions toutes les heures
    echo=False                # Mettre True pour voir les requêtes SQL (debug)
)

# Factory de sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base pour les modèles ORM
Base = declarative_base()

def get_db():
    """
    Générateur de session pour utilisation avec 'with' ou dans FastAPI
    
    Exemple d'utilisation:
    ```python
    from db_connection import get_db
    
    with next(get_db()) as db:
        users = db.query(User).all()
    ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialise toutes les tables dans la base de données
    À exécuter une seule fois au déploiement
    """
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Base de données initialisée avec succès")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation : {e}")
        raise

def test_connection():
    """Test la connexion à la base de données"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Connexion PostgreSQL réussie")
        return True
    except Exception as e:
        print(f"❌ Erreur de connexion PostgreSQL : {e}")
        db.close()
        return False
