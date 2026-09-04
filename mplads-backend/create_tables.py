"""
One-off script to verify the PostgreSQL connection and create the
`projects` table from the SQLAlchemy model.

Run with: python create_tables.py

This is a temporary Day 1 utility. Once Alembic migrations are
introduced later in the project, this script can be retired.
"""

from app.database import Base, engine
from app import models  # noqa: F401  (import needed to register the model with Base)


def main() -> None:
    print(f"Connecting to: {engine.url}")
    with engine.connect() as conn:
        print("Connection successful.")

    print("Creating tables (if they don't already exist)...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created:", list(Base.metadata.tables.keys()))


if __name__ == "__main__":
    main()
