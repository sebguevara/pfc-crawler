from sqlmodel import create_engine, Session
from app.core.config import settings

class _EngineSingleton:
    _engine = None
    @classmethod
    def engine(cls):
        if cls._engine is None:
            cls._engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                echo=False,
            )
        return cls._engine

def get_session():
    return Session(_EngineSingleton.engine())
