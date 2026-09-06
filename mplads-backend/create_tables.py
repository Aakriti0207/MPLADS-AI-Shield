"""
CLI entry point to initialize the database: verifies the PostgreSQL
connection and creates the `projects` table from the SQLAlchemy model
(via app.init_db.init_db()).

Run with: python create_tables.py

This is a Day 1 development utility, not a migration tool. See
app/init_db.py for why Alembic isn't introduced yet.
"""

from app.init_db import init_db

if __name__ == "__main__":
    init_db()
