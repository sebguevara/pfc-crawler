from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import Text
from pgvector.sqlalchemy import Vector

class RagBase(SQLModel):
    pass

class Source(RagBase, table=True):
    __tablename__ = "sources"
    __table_args__ = {"schema": "rag"}

    source_id: UUID = Field(default_factory=uuid4, primary_key=True)
    domain: str = Field(unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    meta: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))

    documents: List["Document"] = Relationship(back_populates="source")

class Document(RagBase, table=True):
    __tablename__ = "documents"
    __table_args__ = {"schema": "rag"}

    doc_id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="rag.sources.source_id")
    url: str
    canonical_url: str = Field(unique=True)
    url_hash: str
    path_segments: List[str] = Field(sa_column=Column(ARRAY(Text)))
    path_depth: int
    title: Optional[str] = None
    page_type: Optional[str] = None
    language: str = Field(default="es")
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    status_code: Optional[int] = None
    content_len: Optional[int] = None
    content_hash: str
    meta: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))

    source: Source = Relationship(back_populates="documents")
    chunks: List["Chunk"] = Relationship(back_populates="document")

class Chunk(RagBase, table=True):
    __tablename__ = "chunks"
    __table_args__ = {"schema": "rag"}

    chunk_id: UUID = Field(default_factory=uuid4, primary_key=True)
    doc_id: UUID = Field(foreign_key="rag.documents.doc_id")
    chunk_index: int
    start_char: int
    end_char: int
    heading_path: List[str] = Field(sa_column=Column(ARRAY(Text)))
    anchor: Optional[str] = None
    text: str
    text_tokens: Optional[int] = None
    is_boilerplate: bool = Field(default=False)
    embedding_model: str
    embedding_dim: int = Field(default=1536)
    embedding: List[float] = Field(sa_column=Column(Vector(1536)))
    meta: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    document: Document = Relationship(back_populates="chunks")