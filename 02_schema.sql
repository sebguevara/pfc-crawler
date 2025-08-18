-- Requiere: CREATE EXTENSION IF NOT EXISTS vector; y schema rag creado

BEGIN;

-- Usuarios (multi-tenant opcional)
CREATE TABLE IF NOT EXISTS rag.users (
  user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id TEXT UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Conversaciones
CREATE TABLE IF NOT EXISTS rag.conversations (
  conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES rag.users(user_id) ON DELETE CASCADE,
  title           TEXT,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ
);

-- Mensajes
CREATE TABLE IF NOT EXISTS rag.messages (
  message_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES rag.conversations(conversation_id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
  text            TEXT NOT NULL,
  tokens          INT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_time ON rag.messages(conversation_id, created_at);

-- Resumen de sesión (1 por conversación)
CREATE TABLE IF NOT EXISTS rag.session_summaries (
  conversation_id UUID PRIMARY KEY REFERENCES rag.conversations(conversation_id) ON DELETE CASCADE,
  summary_text    TEXT NOT NULL,
  summary_tokens  INT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Memorias de largo plazo (por usuario)
-- ¡Ojo! evita llamar la columna "metadata" (confunde a SQLAlchemy); usa "meta".
CREATE TABLE IF NOT EXISTS rag.memories (
  memory_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES rag.users(user_id) ON DELETE CASCADE,
  scope         TEXT NOT NULL CHECK (scope IN ('profile','preference','entity','episodic','commitment')),
  text          TEXT NOT NULL,
  importance    SMALLINT NOT NULL CHECK (importance BETWEEN 1 AND 5),
  usage_count   INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at  TIMESTAMPTZ,
  ttl           INTERVAL,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  embedding     VECTOR(1536) NOT NULL,
  meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
  deleted_at    TIMESTAMPTZ
);

-- Índices recomendados
CREATE INDEX IF NOT EXISTS idx_memories_user ON rag.memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_last_used ON rag.memories(user_id, last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON rag.memories USING GIN(tags);
-- Vector index (elige ivfflat u hnsw según tu Postgres/pgvector)
CREATE INDEX IF NOT EXISTS idx_memories_embedding_ivfflat
  ON rag.memories USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);

COMMIT;
