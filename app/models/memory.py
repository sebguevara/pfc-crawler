from datetime import datetime, timezone
from sqlalchemy import TIMESTAMP
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy import Text
from pgvector.sqlalchemy import Vector

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

# USERS
class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = {"schema": "rag"}
    user_id: UUID = Field(default_factory=uuid4, primary_key=True)
    external_id: str | None = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(TIMESTAMP(timezone=True))
    )

class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "rag"}
    conversation_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="rag.users.user_id", index=True)
    title: str | None = None
    started_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True))
    )

class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = {"schema": "rag"}
    message_id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(foreign_key="rag.conversations.conversation_id", index=True)
    role: str
    text: str
    tokens: int | None = None
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))

class SessionSummary(SQLModel, table=True):
    __tablename__ = "session_summaries"
    __table_args__ = {"schema": "rag"}
    conversation_id: UUID = Field(foreign_key="rag.conversations.conversation_id", primary_key=True)
    summary_text: str
    summary_tokens: int | None = None
    updated_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))

class Memory(SQLModel, table=True):
    __tablename__ = "memories"
    __table_args__ = {"schema": "rag"}
    memory_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="rag.users.user_id", index=True)
    scope: str
    text: str
    importance: int = Field(default=3)
    usage_count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    ttl: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text())))
    embedding: list[float] = Field(sa_column=Column(Vector(dim=1536)))
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True))
    )
