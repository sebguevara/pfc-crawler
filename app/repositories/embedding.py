"""Embedding generation utilities using OpenAI."""
import asyncio
from typing import List
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def embed_texts(texts: List[str], model: str = None) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed
        model: OpenAI embedding model to use (defaults to settings.OPENAI_EMBEDDING_MODEL)

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    if model is None:
        model = settings.OPENAI_EMBEDDING_MODEL

    # Clean texts
    cleaned_texts = [text.replace("\n", " ").strip() for text in texts]

    try:
        response = client.embeddings.create(
            input=cleaned_texts,
            model=model,
            dimensions=settings.EMBEDDING_DIM
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        # Return zero vectors as fallback
        return [[0.0] * settings.EMBEDDING_DIM for _ in texts]

def embed_text(text: str, model: str = None) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text string to embed
        model: OpenAI embedding model to use

    Returns:
        Embedding vector
    """
    embeddings = embed_texts([text], model=model)
    return embeddings[0] if embeddings else [0.0] * settings.EMBEDDING_DIM
