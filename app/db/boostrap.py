from sqlmodel import SQLModel
from app.db.engine import _EngineSingleton

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS rag;

ALTER TABLE sources SET SCHEMA rag;
ALTER TABLE documents SET SCHEMA rag;
ALTER TABLE chunks SET SCHEMA rag;
ALTER TABLE contacts SET SCHEMA rag;

-- tsvector
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

-- índices
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
-- HNSW si tu pgvector lo soporta:
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
  ON rag.chunks USING hnsw (embedding vector_cosine_ops);
"""

def bootstrap_db():
    eng = _EngineSingleton.engine()
    SQLModel.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql(DDL)
