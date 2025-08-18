from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy import Text, Integer
from pgvector.sqlalchemy import Vector

class Source(SQLModel, table=True):
    __tablename__ = "sources"
    __table_args__ = {"schema": "rag"}
    source_id: UUID = Field(default_factory=uuid4, primary_key=True)
    domain: str = Field(index=True, unique=True)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))

class Document(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = {"schema": "rag"}
    doc_id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="rag.sources.source_id", index=True)
    url: str
    canonical_url: str = Field(index=True, unique=True)
    url_hash: str = Field(index=True)
    path_segments: list[str] = Field(sa_column=Column(ARRAY(Text())))
    path_depth: int = Field(sa_column=Column(Integer))
    title: str | None = None
    page_type: str | None = Field(default=None, index=True)
    language: str = Field(default="es")
    fetched_at: datetime | None = Field(sa_column=Column(DateTime(timezone=True)))
    status_code: int | None = None
    content_len: int | None = None
    content_hash: str
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB)
    )

class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    __table_args__ = {"schema": "rag"}
    chunk_id: UUID = Field(default_factory=uuid4, primary_key=True)
    doc_id: UUID = Field(foreign_key="rag.documents.doc_id", index=True)
    chunk_index: int = Field(index=True)
    start_char: int
    end_char: int
    heading_path: list[str] = Field(sa_column=Column(ARRAY(Text())))
    anchor: str | None = None
    text: str
    text_tokens: int | None = None
    is_boilerplate: bool = Field(default=False, index=True)
    embedding_model: str
    embedding_dim: int
    embedding: list[float] = Field(sa_column=Column(Vector(dim=1536)))
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB)
    )
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

class Contact(SQLModel, table=True):
    __tablename__ = "contacts"
    __table_args__ = {"schema": "rag"}
    contact_id: UUID = Field(default_factory=uuid4, primary_key=True)
    doc_id: UUID = Field(foreign_key="rag.documents.doc_id", index=True)
    emails: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text())))
    phones: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text())))
    raw_section: str | None = None
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSONB)
    )
