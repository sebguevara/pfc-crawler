CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE rag.sources (
    source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    domain text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    meta jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE rag.documents (
    doc_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES rag.sources(source_id) ON DELETE CASCADE,
    url text NOT NULL,
    canonical_url text NOT NULL UNIQUE,
    url_hash text NOT NULL,
    path_segments text[] NOT NULL,
    path_depth int NOT NULL,
    title text,
    page_type text,
    language text NOT NULL DEFAULT 'es',
    fetched_at timestamptz NOT NULL DEFAULT now(),
    status_code int,
    content_len int,
    content_hash text NOT NULL,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE rag.chunks (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id uuid NOT NULL REFERENCES rag.documents(doc_id) ON DELETE CASCADE,
    chunk_index int NOT NULL,
    start_char int NOT NULL,
    end_char int NOT NULL,
    heading_path text[] NOT NULL,
    anchor text,
    text text NOT NULL,
    text_tokens int,
    is_boilerplate boolean NOT NULL DEFAULT false,
    embedding_model text NOT NULL,
    embedding_dim int NOT NULL CHECK (embedding_dim = 1536),
    embedding vector(1536) NOT NULL,
    tsv tsvector,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chunks_doc_chunk_idx UNIQUE (doc_id, chunk_index)
);

CREATE TABLE rag.contacts (
    contact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id uuid NOT NULL REFERENCES rag.documents(doc_id) ON DELETE CASCADE,
    emails text[] NOT NULL DEFAULT '{}',
    phones text[] NOT NULL DEFAULT '{}',
    raw_section text,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION rag.update_tsv() RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector('spanish', coalesce(NEW.text,''));
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_chunks_tsv
    BEFORE INSERT OR UPDATE OF text ON rag.chunks
    FOR EACH ROW EXECUTE FUNCTION rag.update_tsv();

CREATE OR REPLACE FUNCTION rag.touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_chunks_touch
    BEFORE UPDATE ON rag.chunks
    FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

CREATE INDEX IF NOT EXISTS documents_source_depth_idx ON rag.documents (source_id, path_depth);
CREATE INDEX IF NOT EXISTS documents_path_segments_gin ON rag.documents USING GIN (path_segments);
CREATE INDEX IF NOT EXISTS documents_meta_gin ON rag.documents USING GIN (meta jsonb_path_ops);
CREATE INDEX IF NOT EXISTS chunks_doc_order_idx ON rag.chunks (doc_id, chunk_index);
CREATE INDEX IF NOT EXISTS chunks_meta_gin ON rag.chunks USING GIN (meta jsonb_path_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON rag.chunks USING GIN (tsv);

DO $$
BEGIN
    BEGIN
        EXECUTE 'CREATE INDEX chunks_embedding_hnsw ON rag.chunks USING hnsw (embedding vector_cosine_ops)';
    EXCEPTION
        WHEN undefined_object OR invalid_schema_name OR feature_not_supported THEN
        EXECUTE 'CREATE INDEX chunks_embedding_ivfflat ON rag.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
    END;
END $$;

ANALYZE rag.sources;
ANALYZE rag.documents;
ANALYZE rag.chunks;

CREATE TABLE IF NOT EXISTS rag.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag.conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES rag.users(user_id) ON DELETE CASCADE,
    title TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag.messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES rag.conversations(conversation_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    text TEXT NOT NULL,
    tokens INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_messages_conv_time ON rag.messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS rag.session_summaries (
    conversation_id UUID PRIMARY KEY REFERENCES rag.conversations(conversation_id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    summary_tokens INT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS rag.memories (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES rag.users(user_id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('profile','preference','entity','episodic','commitment')),
    text TEXT NOT NULL,
    importance SMALLINT NOT NULL CHECK (importance BETWEEN 1 AND 5),
    usage_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    ttl INTERVAL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    embedding VECTOR(1536) NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_memories_user ON rag.memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_last_used ON rag.memories(user_id, last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON rag.memories USING GIN(tags);

DO $$
BEGIN
    BEGIN
        EXECUTE 'CREATE INDEX idx_memories_embedding_hnsw ON rag.memories USING hnsw (embedding vector_cosine_ops)';
    EXCEPTION
        WHEN OTHERS THEN
        EXECUTE 'CREATE INDEX idx_memories_embedding_ivfflat ON rag.memories USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)';
    END;
END $$;