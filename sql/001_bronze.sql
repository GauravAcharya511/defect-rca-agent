CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.nhtsa_recalls_raw (
    campaign_number TEXT NOT NULL, make TEXT NOT NULL, model TEXT NOT NULL, model_year INT NOT NULL,
    payload JSONB NOT NULL, payload_hash CHAR(64) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_number, make, model, model_year)
);

CREATE TABLE IF NOT EXISTS bronze.ingest_audit (
    run_id UUID NOT NULL, source TEXT NOT NULL, make TEXT NOT NULL, model TEXT NOT NULL, model_year INT NOT NULL,
    fetched INT NOT NULL, inserted INT NOT NULL, updated INT NOT NULL, unchanged INT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
