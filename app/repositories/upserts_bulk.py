from typing import Any
from uuid import UUID
from sqlmodel import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.config import settings
from app.models.rag import Source, Document, Chunk

def upsert_source(domain: str, s: Session) -> str:
    t = Source.__table__
    stmt = (
        pg_insert(t)
        .values(domain=domain)
        .on_conflict_do_nothing(index_elements=[t.c.domain])
        .returning(t.c.source_id)
    )
    res = s.exec(stmt).scalar_one_or_none()
    if res:
        return str(res)
    return str(s.exec(t.select().with_only_columns(t.c.source_id).where(t.c.domain==domain)).scalar_one())

def upsert_document(data: dict[str, Any], s: Session) -> str:
    t = Document.__table__
    meta = data.pop("meta", data.pop("metadata", {}))
    payload = {**data, "metadata": meta}

    insert_stmt = pg_insert(t).values(**payload)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[t.c.canonical_url],
        set_={
            "title":         func.coalesce(insert_stmt.excluded.title, t.c.title),
            "page_type":     func.coalesce(insert_stmt.excluded.page_type, t.c.page_type),
            "language":      func.coalesce(insert_stmt.excluded.language, t.c.language),
            "fetched_at":    func.coalesce(insert_stmt.excluded.fetched_at, t.c.fetched_at),
            "status_code":   func.coalesce(insert_stmt.excluded.status_code, t.c.status_code),
            "content_len":   func.coalesce(insert_stmt.excluded.content_len, t.c.content_len),
            "content_hash":  insert_stmt.excluded.content_hash,
            "path_segments": insert_stmt.excluded.path_segments,
            "path_depth":    insert_stmt.excluded.path_depth,
            "metadata":      t.c.metadata.op("||")(insert_stmt.excluded.metadata),
        },
    ).returning(t.c.doc_id)

    return str(s.exec(stmt).scalar_one())

def bulk_upsert_chunks(doc_id: str, rows: list[dict], s: Session) -> int:
    if not rows:
        return 0
    t = Chunk.__table__
    for r in rows:
        r["doc_id"] = UUID(doc_id) if isinstance(doc_id, str) else doc_id
        r.setdefault("embedding_dim", settings.EMBEDDING_DIM)

    insert_stmt = pg_insert(t).values(rows)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[t.c.doc_id, t.c.chunk_index],
        set_={
            "text":           insert_stmt.excluded.text,
            "text_tokens":    insert_stmt.excluded.text_tokens,
            "heading_path":   insert_stmt.excluded.heading_path,
            "anchor":         insert_stmt.excluded.anchor,
            "is_boilerplate": insert_stmt.excluded.is_boilerplate,
            "embedding":      insert_stmt.excluded.embedding,
            "embedding_model":insert_stmt.excluded.embedding_model,
            "embedding_dim":  insert_stmt.excluded.embedding_dim,
            "metadata":       insert_stmt.excluded.metadata,
            "updated_at":     func.now(),
        },
    )
    res = s.exec(stmt)
    return len(rows)
