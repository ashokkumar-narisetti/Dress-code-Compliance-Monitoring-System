"""
migrate.py - Safe migration: creates any new tables without touching existing data.

Run this whenever you add new models (e.g. the 'appeals' table from Phase 2):
    venv\\Scripts\\python migrate.py
"""

from database import Base, engine

print("Running migrations (CREATE TABLE IF NOT EXISTS)…")
Base.metadata.create_all(bind=engine)
print("✅ Migration complete — all tables up to date.")
