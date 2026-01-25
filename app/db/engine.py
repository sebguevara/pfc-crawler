"""Synchronous database engine for legacy code."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from app.core.config import settings

# Create synchronous engine from async URL
sync_db_url = settings.DATABASE_URL

# Ensure we're using the psycopg driver for sync operations
if "postgresql+asyncpg://" in sync_db_url:
    sync_db_url = sync_db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

if "?" in sync_db_url:
    sync_db_url = sync_db_url.split("?")[0]

# Create synchronous engine
engine = create_engine(
    sync_db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "options": "-c search_path=rag,public"
    }
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@contextmanager
def get_session() -> Session:
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            # use session
            session.commit()
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
