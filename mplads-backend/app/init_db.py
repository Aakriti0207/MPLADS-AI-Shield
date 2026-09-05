"""
Database initialization logic for the MPLADS AI backend.

Day 1 approach: use SQLAlchemy's metadata.create_all() to create tables
directly from the models. This is the standard "development-friendly"
approach for an early-stage project with a single table and no
production data yet.

Why not Alembic yet:
    Alembic earns its keep once you have (a) real data in the database
    that must be preserved across schema changes, and/or (b) multiple
    environments/collaborators whose schemas need to move forward in
    lockstep via versioned migration files. On Day 1 we have neither -
    there's one table, no data to preserve, and the model in models.py
    IS the source of truth. create_all() is simpler, has zero extra
    dependencies, and is exactly what SQLAlchemy recommends for this
    stage. We should introduce Alembic as soon as we (a) have data
    worth preserving, or (b) start actively evolving the schema
    (adding project_progress, alerts, etc. in later phases) — create_all()
    only ever creates missing tables, it never alters or drops existing
    ones, so it cannot handle schema changes safely once real data
    exists.

This module is import-safe: importing it does NOT touch the database.
Only calling init_db() does. That makes it safe to import from
create_tables.py (a manual script) and, later, from main.py if we want
a startup-safe auto-create hook for local dev.
"""

import logging

from sqlalchemy.exc import OperationalError

from app.database import Base, engine

# Import models so they register their tables on Base.metadata.
# Required even though `models` isn't referenced directly below.
from app import models  # noqa: F401

logger = logging.getLogger("mplads.init_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def init_db() -> None:
    """
    Create all tables defined on Base.metadata that don't already exist.

    Safe to call multiple times - create_all() only creates tables that
    are missing; it does not touch tables that already exist, and it
    never drops or alters anything. This makes it safe to call on every
    app startup during development.
    """
    logger.info("Connecting to database: %s", engine.url)
    try:
        with engine.connect():
            logger.info("Connection successful.")
    except OperationalError as exc:
        logger.error("Could not connect to the database.")
        logger.error(
            "Check that: (1) PostgreSQL is running, (2) DATABASE_URL in "
            ".env has the correct user/password/host/port/dbname, "
            "(3) the database itself has been created."
        )
        raise exc

    logger.info("Creating tables (if they don't already exist)...")
    Base.metadata.create_all(bind=engine)
    table_names = list(Base.metadata.tables.keys())
    logger.info("Done. Tables now present in metadata: %s", table_names)


if __name__ == "__main__":
    init_db()
