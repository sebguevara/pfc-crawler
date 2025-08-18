# app/services/retrieval.py
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.db.engine import get_session
from app.models.rag import Chunk, Document

_embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL)

def kb_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    q_vec = _embeddings.embed_query(query)

    c = Chunk.__table__.c
    d = Document.__table__.c

    dist = c.embedding.cosine_distance(q_vec).label("distance")
    sim  = (1 - c.embedding.cosine_distance(q_vec)).label("similarity")

    stmt = (
        select(
            c.chunk_id,
            c.text,
            d.title,
            d.canonical_url,
            sim,
        )
        .select_from(Chunk.__table__.join(Document.__table__, d.doc_id == c.doc_id))
        .where(c.is_boilerplate == False)
        .order_by(dist)
        .limit(int(k))
    )

    with get_session() as s:
        rows = s.execute(stmt).all()

    return [
        {
            "chunk_id": str(row[0]),
            "text": row[1],
            "title": row[2],
            "canonical_url": row[3],
            "similarity": float(row[4]),
        }
        for row in rows
    ]
