-- Stage 3: complaint narratives embedded for semantic retrieval.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;

-- One row per complaint x vehicle x chunk x embedding model.
CREATE TABLE IF NOT EXISTS rag.complaint_chunks (
    odi_number       BIGINT      NOT NULL,
    make             TEXT        NOT NULL,
    model            TEXT        NOT NULL,
    model_year       INT         NOT NULL,
    chunk_no         INT         NOT NULL,
    embed_model      TEXT        NOT NULL,
    component_groups TEXT[]      NOT NULL,
    chunk_text       TEXT        NOT NULL,
    source_hash      CHAR(64)    NOT NULL,
    embedding        vector(384) NOT NULL,
    embedded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (odi_number, make, model, model_year, chunk_no, embed_model)
);

-- One HNSW index per embedding model (partial), so a query for one model never
-- wades through the other model's vectors. Cosine distance (<=>) on normalized vectors.
CREATE INDEX IF NOT EXISTS complaint_chunks_minilm_hnsw
    ON rag.complaint_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embed_model = 'all-MiniLM-L6-v2';
CREATE INDEX IF NOT EXISTS complaint_chunks_hash_hnsw
    ON rag.complaint_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embed_model = 'hashing-bow-384';
