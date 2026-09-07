"""
Minimal, additive schema synchronization for the `projects` table.

Why this exists:
    SQLAlchemy's `Base.metadata.create_all()` (used by app/init_db.py)
    only ever CREATES tables that don't exist yet - it never ALTERs a
    table that's already there. That's fine on Day 1 with an empty dev
    database, but the moment a real `projects` table already exists
    (with data in it), adding the Phase 2 columns to app/models.py alone
    does nothing to the actual database schema until something runs the
    matching ALTER TABLE statements.

What this does (and does not do):
    - It is NOT a general-purpose migration framework. It does not do
      versioned migrations, downgrades, or track migration history.
    - It only handles the two additive changes Phase 2 needs:
        1. Adding any column that's defined on the `Project` model but
           missing from the actual `projects` table (ADD COLUMN).
        2. Relaxing `state`/`district` from NOT NULL to NULL-able, if the
           existing table still has the old Day 1 constraint.
    - It never drops columns, never drops/recreates tables with data in
      them, and never touches any table other than `projects`.
    - It is safe to call repeatedly: on the first call it does the work;
      on every call after that, it finds nothing left to do and is a
      no-op.

    Per the Phase 2 integration brief: "Do not introduce a large
    migration framework unless the existing project already uses one."
    This project doesn't use Alembic (see app/init_db.py's docstring for
    why), so this lightweight approach is the intentional choice rather
    than a placeholder for something bigger.

Dialect coverage:
    - PostgreSQL (the project's real target): both ADD COLUMN and DROP
      NOT NULL are fully supported and handled below.
    - SQLite (used for local testing per the Phase 2 test plan): ADD
      COLUMN is supported and handled below. SQLite does not support
      `ALTER TABLE ... ALTER COLUMN ... DROP NOT NULL` without a full
      table rebuild (create new table, copy rows, drop old, rename).
      Implementing that rebuild was judged out of scope for a "smallest
      safe" migration helper whose real target is Postgres - a fresh
      SQLite database created via create_all() already gets the correct
      nullable columns from app/models.py directly, so this limitation
      only affects the (uncommon, dev-only) case of an *existing* SQLite
      database created before this Phase 2 change. That case logs a
      clear warning rather than silently doing nothing.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database import Base, engine as default_engine

# Import models so Project is registered on Base.metadata.
from app.models import Project  # noqa: F401

logger = logging.getLogger("mplads.schema_migration")

TABLE_NAME = "projects"

# Columns that changed from NOT NULL -> NULL-able in the Phase 2 update.
# (See app/models.py for why: real Phase 2 projects can lack a state
# value, and none of them have a district value at all.)
COLUMNS_TO_RELAX = ("state", "district")


def _column_add_ddl(engine: Engine, column) -> str:
    """Build the `<name> <type> [NOT NULL DEFAULT ...]` fragment for one column."""
    coltype = column.type.compile(dialect=engine.dialect)
    fragment = f"{column.name} {coltype}"

    if not column.nullable:
        # Only expected for is_synthetic today. A NOT NULL column added to
        # a table that already has rows MUST carry a DEFAULT, or the ADD
        # COLUMN itself would fail against existing rows.
        if column.name == "is_synthetic":
            default_literal = "0" if engine.dialect.name == "sqlite" else "FALSE"
            fragment += f" NOT NULL DEFAULT {default_literal}"
        else:  # pragma: no cover - defensive; no other NOT NULL Phase 2 columns exist
            logger.warning(
                "Column %s is NOT NULL with no known default; adding as "
                "NULL-able instead to avoid breaking existing rows.",
                column.name,
            )
    return fragment


def _add_missing_columns(engine: Engine, existing_col_names: set) -> list:
    added = []
    model_columns = Project.__table__.columns
    with engine.begin() as conn:
        for column in model_columns:
            if column.name in existing_col_names:
                continue
            ddl = _column_add_ddl(engine, column)
            conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {ddl}"))
            added.append(column.name)
            logger.info("Added column %s.%s", TABLE_NAME, column.name)
    return added


def _relax_not_null_columns(engine: Engine, existing_columns_info: dict) -> list:
    relaxed = []
    dialect = engine.dialect.name
    for col_name in COLUMNS_TO_RELAX:
        info = existing_columns_info.get(col_name)
        if info is None or info.get("nullable", True):
            continue  # column missing (handled above) or already nullable

        if dialect == "postgresql":
            with engine.begin() as conn:
                conn.execute(
                    text(f"ALTER TABLE {TABLE_NAME} ALTER COLUMN {col_name} DROP NOT NULL")
                )
            relaxed.append(col_name)
            logger.info("Relaxed %s.%s to NULL-able.", TABLE_NAME, col_name)
        elif dialect == "sqlite":
            logger.warning(
                "%s.%s is still NOT NULL in this existing SQLite database. "
                "SQLite cannot drop a NOT NULL constraint without a full "
                "table rebuild, which this lightweight sync intentionally "
                "does not perform. This only matters for a SQLite database "
                "created before the Phase 2 change; a fresh database (or "
                "Postgres) is unaffected. Recreate the local SQLite file if "
                "you need this relaxed, or use Postgres for anything beyond "
                "quick local testing.",
                TABLE_NAME,
                col_name,
            )
        else:  # pragma: no cover - project only targets postgres/sqlite
            logger.warning(
                "Unsupported dialect '%s' for relaxing NOT NULL on %s.%s; skipping.",
                dialect,
                TABLE_NAME,
                col_name,
            )
    return relaxed


def sync_schema(engine: Engine = None) -> dict:
    """
    Bring an existing `projects` table up to date with app/models.py,
    additively and idempotently.

    Returns a small report dict describing what (if anything) was done,
    so callers (create_tables.py, import_phase2.py) can log it.
    """
    engine = engine or default_engine
    inspector = inspect(engine)

    if not inspector.has_table(TABLE_NAME):
        logger.info("%s table does not exist yet; creating it fresh.", TABLE_NAME)
        Base.metadata.create_all(bind=engine)
        return {"created_fresh": True, "columns_added": [], "constraints_relaxed": []}

    existing_columns_info = {c["name"]: c for c in inspector.get_columns(TABLE_NAME)}
    columns_added = _add_missing_columns(engine, set(existing_columns_info.keys()))

    # Re-inspect if we just added columns, so nullability checks below see
    # the current state (not strictly needed for state/district since they
    # were pre-existing, but keeps this function correct if that ever changes).
    if columns_added:
        existing_columns_info = {c["name"]: c for c in inspector.get_columns(TABLE_NAME)}

    constraints_relaxed = _relax_not_null_columns(engine, existing_columns_info)

    return {
        "created_fresh": False,
        "columns_added": columns_added,
        "constraints_relaxed": constraints_relaxed,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = sync_schema()
    print(result)
