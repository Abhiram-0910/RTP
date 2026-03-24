CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE media ADD COLUMN IF NOT EXISTS embedding vector(384);
ALTER TABLE media ADD COLUMN IF NOT EXISTS embedding_gemini vector(768);
DROP INDEX IF EXISTS media_embedding_hnsw_idx;
CREATE INDEX media_embedding_hnsw_idx ON media USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
