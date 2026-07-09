"""
Database setup. Works with SQLite locally (zero setup) and Postgres in
production (set DATABASE_URL). Tables are created automatically on startup,
so there's no separate migration step to run or forget.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


def _normalize_db_url(url: str) -> str:
    # Some providers (older Heroku-style URLs) hand out "postgres://",
    # but SQLAlchemy 2.x requires the "postgresql://" scheme.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = _normalize_db_url(settings.DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models_db  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
