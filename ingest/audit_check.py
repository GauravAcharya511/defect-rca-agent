"""
Completeness gate: fail the pipeline if the latest complaints load left any configured
vehicle-year empty. This is the check that would have caught the API's silent HTTP 400s.
"""
import json, os, sys
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parent.parent
DSN = os.getenv("PG_DSN", "postgresql://rca:rca@localhost:5433/rca")

LATEST_RUN = """
SELECT run_id FROM bronze.ingest_audit
WHERE source LIKE 'complaints_flat:%'
ORDER BY run_at DESC LIMIT 1
"""
PER_VEHICLE = """
SELECT make, model, model_year, sum(fetched) AS fetched
FROM bronze.ingest_audit
WHERE run_id = %s
GROUP BY 1, 2, 3
"""


def main() -> int:
    wanted = {(v["make"].upper(), v["model"].upper(), y)
              for v in json.loads((ROOT / "config" / "vehicles.json").read_text()) for y in v["years"]}
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(LATEST_RUN)
        row = cur.fetchone()
        if row is None:
            print("FAIL: no complaints ingestion run found in bronze.ingest_audit")
            return 1
        cur.execute(PER_VEHICLE, (row[0],))
        counts = {(m, mo, y): f for m, mo, y, f in cur.fetchall()}
    empty = sorted(k for k in wanted if counts.get(k, 0) == 0)
    print(f"run_id={row[0]} vehicle-years={len(wanted)} empty={len(empty)}")
    for k in sorted(wanted):
        print(f"  {k[0]} {k[1]} {k[2]}: {counts.get(k, 0)} complaint rows")
    if empty:
        print("FAIL: vehicle-years with zero complaints:", ", ".join(" ".join(map(str, e)) for e in empty))
        return 1
    print("PASS: every configured vehicle-year has complaints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
