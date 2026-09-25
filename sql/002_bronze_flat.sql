CREATE TABLE IF NOT EXISTS bronze.nhtsa_complaints_flat (
    odi_number BIGINT NOT NULL, component TEXT NOT NULL,
    make TEXT NOT NULL, model TEXT NOT NULL, model_year INT NOT NULL,
    source_file TEXT NOT NULL, payload JSONB NOT NULL, payload_hash CHAR(64) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (odi_number, component, make, model, model_year)
);
