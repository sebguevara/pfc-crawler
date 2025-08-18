from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    LLM_MODEL: str = "gpt-4o-mini"
    TOP_K_CHUNKS: int = 8
    TOP_K_MEMORIES: int = 8
    MEMORY_SCORE_THRESHOLD: float = 0.55
    MEMORY_RECENCY_TAU_DAYS: int = 7
    SUMMARY_TURN_INTERVAL: int = 8

    SITE_MD_DIR: str = "site_md"

    class Config:
        env_file = ".env"

settings = Settings()
