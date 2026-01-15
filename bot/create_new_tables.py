# bot/create_new_tables.py
from db_connection import Base, engine

# Créer toutes les tables
Base.metadata.create_all(engine)
print("✅ Tables créées avec succès")
