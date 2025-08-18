-- 1) esquema
CREATE SCHEMA IF NOT EXISTS rag;

-- (opcional) hacer que el search_path priorice rag a nivel DB
-- ALTER DATABASE "YOUR_DB" SET search_path = rag, public;

-- 2) tablas

-- fuentes / dominios
CREATE TABLE rag.sources (
  source_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain      text NOT NULL UNIQUE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  meta        jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- documentos (1 por URL canónica)
CREATE TABLE rag.documents (
  doc_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id     uuid NOT NULL REFERENCES rag.sources(source_id) ON DELETE CASCADE,
  url           text NOT NULL,
  canonical_url text NOT NULL UNIQUE,
  url_hash      text NOT NULL,
  path_segments text[] NOT NULL,
  path_depth    int   NOT NULL,
  title         text,
  page_type     text,
  language      text NOT NULL DEFAULT 'es',
  fetched_at    timestamptz NOT NULL DEFAULT now(),
  status_code   int,
  content_len   int,
  content_hash  text NOT NULL,
  meta      jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- chunks indexables (para embeddings)
CREATE TABLE rag.chunks (
  chunk_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id          uuid NOT NULL REFERENCES rag.documents(doc_id) ON DELETE CASCADE,
  chunk_index     int  NOT NULL,
  start_char      int  NOT NULL,
  end_char        int  NOT NULL,
  heading_path    text[] NOT NULL,
  anchor          text,
  text            text NOT NULL,
  text_tokens     int,
  is_boilerplate  boolean NOT NULL DEFAULT false,
  embedding_model text NOT NULL,
  embedding_dim   int  NOT NULL CHECK (embedding_dim = 1536),
  embedding       vector(1536) NOT NULL,
  meta        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chunks_doc_chunk_idx UNIQUE (doc_id, chunk_index)
);

-- contactos detectados (opcional)
CREATE TABLE rag.contacts (
  contact_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id      uuid NOT NULL REFERENCES rag.documents(doc_id) ON DELETE CASCADE,
  emails      text[] NOT NULL DEFAULT '{}',
  phones      text[] NOT NULL DEFAULT '{}',
  raw_section text,
  meta    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- 3) FTS (tsvector + trigger)
ALTER TABLE rag.chunks ADD COLUMN IF NOT EXISTS tsv tsvector;

CREATE OR REPLACE FUNCTION rag.update_tsv() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('spanish', coalesce(NEW.text,''));
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_tsv ON rag.chunks;
CREATE TRIGGER trg_chunks_tsv
  BEFORE INSERT OR UPDATE OF text ON rag.chunks
  FOR EACH ROW EXECUTE FUNCTION rag.update_tsv();

-- 4) trigger de updated_at
CREATE OR REPLACE FUNCTION rag.touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_touch ON rag.chunks;
CREATE TRIGGER trg_chunks_touch
  BEFORE UPDATE ON rag.chunks
  FOR EACH ROW EXECUTE FUNCTION rag.touch_updated_at();

-- 5) índices de navegación / metadata / FTS
CREATE INDEX IF NOT EXISTS documents_source_depth_idx
  ON rag.documents (source_id, path_depth);

CREATE INDEX IF NOT EXISTS documents_path_segments_gin
  ON rag.documents USING GIN (path_segments);

CREATE INDEX IF NOT EXISTS documents_metadata_gin
  ON rag.documents USING GIN (metadata jsonb_path_ops);

CREATE INDEX IF NOT EXISTS chunks_doc_order_idx
  ON rag.chunks (doc_id, chunk_index);

CREATE INDEX IF NOT EXISTS chunks_metadata_gin
  ON rag.chunks USING GIN (metadata jsonb_path_ops);

CREATE INDEX IF NOT EXISTS chunks_tsv_gin
  ON rag.chunks USING GIN (tsv);

-- 6) índice vectorial: intenta HNSW y si no, cae a IVFFlat
DO $$
BEGIN
  BEGIN
    EXECUTE 'CREATE INDEX chunks_embedding_hnsw
             ON rag.chunks USING hnsw (embedding vector_cosine_ops)';
  EXCEPTION
    WHEN undefined_object OR invalid_schema_name OR feature_not_supported THEN
      -- Fallback si tu pgvector no trae HNSW
      EXECUTE 'CREATE INDEX chunks_embedding_ivfflat
               ON rag.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
  END;
END $$;

-- 7) stats
ANALYZE rag.sources;
ANALYZE rag.documents;
ANALYZE rag.chunks;
