"""Database upsert operations for sources, documents, and chunks."""
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import uuid

def upsert_source(domain: str, session: Session) -> uuid.UUID:
    """
    Insert or get existing source by domain.

    Args:
        domain: Domain name (e.g., 'example.com')
        session: Database session

    Returns:
        source_id UUID
    """
    # Check if source exists
    result = session.execute(
        "SELECT source_id FROM rag.sources WHERE domain = :domain",
        {"domain": domain}
    )
    row = result.fetchone()

    if row:
        return row[0]

    # Insert new source
    source_id = uuid.uuid4()
    session.execute(
        "INSERT INTO rag.sources (source_id, domain) VALUES (:id, :domain)",
        {"id": source_id, "domain": domain}
    )
    return source_id

def upsert_document(doc_data: Dict[str, Any], session: Session) -> uuid.UUID:
    """
    Insert or update document.

    Args:
        doc_data: Dictionary with document fields
        session: Database session

    Returns:
        doc_id UUID
    """
    canonical_url = doc_data.get("canonical_url")

    # Check if document exists by canonical URL
    result = session.execute(
        "SELECT doc_id FROM rag.documents WHERE canonical_url = :url",
        {"url": canonical_url}
    )
    row = result.fetchone()

    if row:
        doc_id = row[0]
        # Update existing document
        session.execute(
            """
            UPDATE rag.documents SET
                title = :title,
                fetched_at = :fetched_at,
                status_code = :status_code,
                content_len = :content_len,
                content_hash = :content_hash,
                meta = :meta
            WHERE doc_id = :doc_id
            """,
            {
                "doc_id": doc_id,
                "title": doc_data.get("title"),
                "fetched_at": doc_data.get("fetched_at"),
                "status_code": doc_data.get("status_code"),
                "content_len": doc_data.get("content_len"),
                "content_hash": doc_data.get("content_hash"),
                "meta": doc_data.get("metadata", {})
            }
        )
        return doc_id

    # Insert new document
    doc_id = uuid.uuid4()
    session.execute(
        """
        INSERT INTO rag.documents (
            doc_id, source_id, url, canonical_url, url_hash,
            path_segments, path_depth, title, page_type, language,
            fetched_at, status_code, content_len, content_hash, meta
        ) VALUES (
            :doc_id, :source_id, :url, :canonical_url, :url_hash,
            :path_segments, :path_depth, :title, :page_type, :language,
            :fetched_at, :status_code, :content_len, :content_hash, :meta
        )
        """,
        {
            "doc_id": doc_id,
            "source_id": doc_data.get("source_id"),
            "url": doc_data.get("url"),
            "canonical_url": canonical_url,
            "url_hash": doc_data.get("url_hash"),
            "path_segments": doc_data.get("path_segments", []),
            "path_depth": doc_data.get("path_depth", 0),
            "title": doc_data.get("title"),
            "page_type": doc_data.get("page_type"),
            "language": doc_data.get("language", "es"),
            "fetched_at": doc_data.get("fetched_at"),
            "status_code": doc_data.get("status_code"),
            "content_len": doc_data.get("content_len"),
            "content_hash": doc_data.get("content_hash"),
            "meta": doc_data.get("metadata", {})
        }
    )
    return doc_id

def bulk_upsert_chunks(doc_id: uuid.UUID, chunks: List[Dict[str, Any]], session: Session) -> int:
    """
    Bulk insert or replace chunks for a document.

    Args:
        doc_id: Document ID
        chunks: List of chunk dictionaries
        session: Database session

    Returns:
        Number of chunks inserted
    """
    if not chunks:
        return 0

    # Delete existing chunks for this document
    session.execute(
        "DELETE FROM rag.chunks WHERE doc_id = :doc_id",
        {"doc_id": doc_id}
    )

    # Prepare chunks for bulk insert
    for chunk in chunks:
        chunk_id = uuid.uuid4()
        session.execute(
            """
            INSERT INTO rag.chunks (
                chunk_id, doc_id, chunk_index, start_char, end_char,
                heading_path, anchor, text, text_tokens, is_boilerplate,
                embedding_model, embedding_dim, embedding, meta
            ) VALUES (
                :chunk_id, :doc_id, :chunk_index, :start_char, :end_char,
                :heading_path, :anchor, :text, :text_tokens, :is_boilerplate,
                :embedding_model, :embedding_dim, :embedding, :meta
            )
            """,
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "chunk_index": chunk["chunk_index"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "heading_path": chunk["heading_path"],
                "anchor": chunk.get("anchor"),
                "text": chunk["text"],
                "text_tokens": chunk["text_tokens"],
                "is_boilerplate": chunk.get("is_boilerplate", False),
                "embedding_model": chunk["embedding_model"],
                "embedding_dim": 1536,
                "embedding": chunk["embedding"],
                "meta": chunk.get("metadata", {})
            }
        )

    return len(chunks)
