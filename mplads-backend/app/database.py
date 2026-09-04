"""
Database configuration for the MPLADS AI backend.

Loads DATABASE_URL from .env and sets up the SQLAlchemy engine,
session factory, and declarative base used throughout the app.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env at project root
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Create a .env file (see .env.example) "
        "with a valid PostgreSQL connection string."
    )

# pool_pre_ping avoids using stale/dead connections from the pool
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
