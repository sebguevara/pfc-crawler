from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"  # Mejor calidad que small
    EMBEDDING_DIM: int = 1536  # Mantener 1536 con shortening para compatibilidad
    SITE_MD_DIR: str = "med_site"  # Carpeta para archivos de med.unne.edu.ar
    TOP_K_CHUNKS: int = 8
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()