from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings
from app.db.engine import get_session
from app.repositories.md_parser import read_md, split_by_headings
from app.repositories.chunker import make_chunks
from app.repositories.embedding import embed_texts
from app.repositories.upserts_bulk import (
    upsert_source, upsert_document, bulk_upsert_chunks
)
from app.utils.urls import canonicalize, path_segments, page_type_from_path, url_hash

def ingest_folder(folder: str | Path):
    folder = Path(folder)
    files = sorted(folder.glob("*.md"))
    if not files:
        return {"docs": 0, "chunks": 0}

    total_chunks = 0
    with get_session() as s:
        for p in files:
            title, url, body, content_hash = read_md(p)
            if not url:
                continue

            can   = canonicalize(url)
            segs  = path_segments(can)
            ptype = page_type_from_path(segs)
            domain = can.split("/")[2]

            source_id = upsert_source(domain, s)
            doc_data = dict(
                source_id=source_id,
                url=url,
                canonical_url=can,
                url_hash=url_hash(can),
                path_segments=segs,
                path_depth=len(segs),
                title=title,
                page_type=ptype,
                language="es",
                fetched_at=datetime.now(timezone.utc),
                status_code=200,
                content_len=len(body),
                content_hash=content_hash,
                metadata={}
            )
            doc_id = upsert_document(doc_data, s)

            chunks_raw = []
            idx = 0
            for heading_path, start, end, seg_text in split_by_headings(body):
                for piece, tok_count in make_chunks(seg_text, heading_path, start):
                    meta = {
                        "url": can,
                        "title": title,
                        "page_type": ptype,
                        "path_segments": segs,
                        "path_depth": len(segs),
                        "heading_path": heading_path,
                    }
                    chunks_raw.append({
                        "chunk_index": idx,
                        "start_char": start,
                        "end_char":   end,
                        "heading_path": heading_path,
                        "anchor": None,
                        "text": piece,
                        "text_tokens": tok_count,
                        "is_boilerplate": False,
                        "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
                        "embedding": [],
                        "metadata": meta
                    })
                    idx += 1

            if chunks_raw:
                texts = [c["text"] for c in chunks_raw]
                embs  = embed_texts(texts)
                for c, e in zip(chunks_raw, embs):
                    c["embedding"] = e

                total_chunks += bulk_upsert_chunks(doc_id, chunks_raw, s)

        s.commit()
    return {"docs": len(files), "chunks": total_chunks}
