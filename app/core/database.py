from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, text
from app.core.config import settings

db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")

db_url = db_url.replace("localhost", "127.0.0.1")

if "?" in db_url:
    db_url = db_url.split("?")[0]

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args={
        "server_settings": {
            "search_path": "rag,public"
        }
    }
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

async def init_rag_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS rag"))
        await conn.run_sync(SQLModel.metadata.create_all)