from app.core.openai import client
from app.core.config import settings

def embed_texts(texts: list[str]) -> list[list[float]]:
    resp = client().embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts
    )
    return [d.embedding for d in resp.data]