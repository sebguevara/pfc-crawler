from typing import List, Optional, Set
from urllib.parse import urlparse
from sqlmodel import select, col, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rag import Document, Chunk, Source
from app.utils.urls import canonicalize, path_segments, page_type_from_path, url_hash

class RagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_source(self, url: str) -> Source:
        """Get or create a source from a URL's domain."""
        domain = urlparse(url).netloc
        statement = select(Source).where(Source.domain == domain)
        result = await self.session.execute(statement)
        source = result.scalar_one_or_none()

        if not source:
            source = Source(domain=domain)
            self.session.add(source)
            await self.session.flush()

        return source

    async def get_doc_by_hash(self, hash_str: str) -> Optional[Document]:
        statement = select(Document).where(Document.content_hash == hash_str)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_doc_by_canonical_url(self, canonical_url: str) -> Optional[Document]:
        statement = select(Document).where(Document.canonical_url == canonical_url)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_document(self, doc: Document) -> Document:
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def create_chunks(self, chunks: List[Chunk]):
        self.session.add_all(chunks)

    async def get_full_document_text(self, doc_id: str) -> str:
        statement = (
            select(Chunk.text)
            .where(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
        )
        result = await self.session.execute(statement)
        texts = result.scalars().all()
        return "\n".join(texts)

    async def hybrid_search(self, vector: List[float], query_text: str, limit: int) -> List[Chunk]:
        vec_stmt = (
            select(Chunk)
            .order_by(col(Chunk.embedding).cosine_distance(vector))
            .limit(limit)
        )
        vec_result = await self.session.execute(vec_stmt)
        vec_chunks = vec_result.scalars().all()

        kw_stmt = (
            select(Chunk)
            .where(text("to_tsvector('spanish', text) @@ websearch_to_tsquery('spanish', :q)"))
            .limit(limit)
        )
        kw_result = await self.session.execute(kw_stmt, {"q": query_text})
        kw_chunks = kw_result.scalars().all()

        seen_ids: Set[str] = set()
        final_results = []

        for c in vec_chunks:
            if c.chunk_id not in seen_ids:
                final_results.append(c)
                seen_ids.add(c.chunk_id)

        for c in kw_chunks:
            if c.chunk_id not in seen_ids:
                final_results.append(c)
                seen_ids.add(c.chunk_id)

        return final_results