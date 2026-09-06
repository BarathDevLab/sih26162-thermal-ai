"""
Database Session and Connection Management
Configures SQLAlchemy engine, session maker, and FastAPI dependency injection.
Supports PostgreSQL/PostGIS in production with SQLite fallback for offline development.
"""

import os
import logging
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables
_curr = Path(__file__).resolve()
for _candidate in [
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
    _curr.parents[2] / ".env",
    _curr.parents[3] / ".env",
    _curr.parents[3] / "backend" / ".env"
]:
    if _candidate.exists():
        load_dotenv(str(_candidate))

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./data/sih26162.db"
)

# SQLite concurrency and path fixes
connect_args = {}
if DEFAULT_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    # Ensure local directory exists
    db_path = DEFAULT_DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

engine = create_engine(
    DEFAULT_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_postgis_available(target_engine=None) -> bool:
    """
    Checks if PostGIS extension is installed and available in the current database.
    """
    eng = target_engine or engine
    if not eng.url.drivername.startswith("postgresql"):
        return False
    try:
        with eng.connect() as conn:
            res = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'"))
            return res.scalar() == 1
    except Exception:
        return False


def init_db(target_engine=None):
    """
    Initializes database schema, attempting to enable PostGIS if on PostgreSQL.
    """
    eng = target_engine or engine
    if eng.url.drivername.startswith("postgresql"):
        try:
            with eng.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                logger.info("PostGIS extension checked/created.")
        except Exception as e:
            logger.warning(f"Notice: PostGIS extension not initialized ({e}). Using standard spatial indexing.")

    Base.metadata.create_all(bind=eng)
    logger.info("Database tables initialized.")
