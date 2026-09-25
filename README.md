# Defect Root-Cause Analysis Platform

Vehicle defect investigation platform on public NHTSA complaint and recall data: ingestion,
dbt medallion models, and (in progress) a retrieval-augmented agent that drafts preliminary
root-cause reports for engineering review.

## Status
| Stage | Scope | Status |
|---|---|---|
| 1 | Ingestion: recalls via NHTSA REST API, complaints via NHTSA bulk flat files; SHA-256 idempotent upserts, retry/backoff, per-run audit table | Done |
| 2 | dbt silver/gold models, component hotspot index, data-quality tests; Airflow orchestration | In progress |
| 3 | Embeddings + pgvector retrieval | Planned |
| 4 | Tool-calling RCA agent with engineering-review handoff | Planned |
| 5 | Evaluation harness (accuracy, groundedness, abstention) with CI gate | Planned |
| 6 | FastAPI (REST + WebSocket) + React investigation UI | Planned |
| 7 | Kubernetes deployment + Prometheus/Grafana | Planned |

## Notable decision
The per-vehicle complaints API returns HTTP 400 for high-volume vehicles (e.g. Tesla Model Y 2021).
The first loader treated that as "no records", and the audit table showed zero complaints for
5 of 12 vehicle-years. Complaints now load from NHTSA's bulk flat files; recalls stay on the API,
and HTTP 400 responses are logged instead of swallowed.

## Metric caveat
NHTSA publishes no fleet sizes, so `gold.agg_component_hotspots` reports complaint *share* against
a cross-vehicle baseline (`hotspot_ix`), not a true failure rate.

## Run locally
```bash
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 ingest/nhtsa_ingest.py          # recalls
python3 ingest/nhtsa_flat_ingest.py     # complaints
cd dbt && dbt build --profiles-dir .    # separate venv: dbt-core 1.12.5, dbt-postgres 1.11.0
```

Data: NHTSA Office of Defects Investigation public datasets.
