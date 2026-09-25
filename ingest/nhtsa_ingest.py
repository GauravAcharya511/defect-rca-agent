import hashlib, json, logging, os, sys, time, uuid
from pathlib import Path
import psycopg, requests
from psycopg.types.json import Jsonb

BASE = "https://api.nhtsa.gov"
COMPLAINTS_URL = f"{BASE}/complaints/complaintsByVehicle"
RECALLS_URL = f"{BASE}/recalls/recallsByVehicle"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "vehicles.json"
DSN = os.getenv("PG_DSN", "postgresql://rca:rca@localhost:5433/rca")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("nhtsa_ingest")

def fetch(url, params, max_retries=5):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"retryable status {resp.status_code}")
            if resp.status_code == 400:
                return []
            resp.raise_for_status()
            return resp.json().get("results") or []
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            wait = 2 ** attempt
            log.warning("fetch failed (%s), attempt %d/%d, sleeping %ds", exc, attempt + 1, max_retries, wait)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url} {params}")

def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

UPSERT = """
INSERT INTO bronze.{table} ({key_col}, make, model, model_year, payload, payload_hash)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT ({key_col}, make, model, model_year) DO UPDATE
   SET payload = EXCLUDED.payload, payload_hash = EXCLUDED.payload_hash, updated_at = now()
 WHERE bronze.{table}.payload_hash <> EXCLUDED.payload_hash
RETURNING (xmax = 0) AS inserted
"""
SOURCES = [
    ("complaints", COMPLAINTS_URL, UPSERT.format(table="nhtsa_complaints_raw", key_col="odi_number"), "odiNumber"),
    ("recalls", RECALLS_URL, UPSERT.format(table="nhtsa_recalls_raw", key_col="campaign_number"), "NHTSACampaignNumber"),
]

def load(cur, sql, key_field, rows, make, model, year):
    ins = upd = same = 0
    for row in rows:
        key = row.get(key_field)
        if key is None:
            log.warning("skipping record without %s", key_field); continue
        cur.execute(sql, (key, make, model, year, Jsonb(row), payload_hash(row)))
        res = cur.fetchone()
        if res is None: same += 1
        elif res[0]: ins += 1
        else: upd += 1
    return ins, upd, same

def run():
    vehicles = json.loads(CONFIG.read_text())
    run_id = uuid.uuid4()
    log.info("run_id=%s vehicles=%d", run_id, len(vehicles))
    with psycopg.connect(DSN) as conn:
        for v in vehicles:
            for year in v["years"]:
                params = {"make": v["make"], "model": v["model"], "modelYear": year}
                for source, url, sql, key in SOURCES:
                    rows = fetch(url, params)
                    with conn.transaction(), conn.cursor() as cur:
                        ins, upd, same = load(cur, sql, key, rows, v["make"], v["model"], year)
                        cur.execute("INSERT INTO bronze.ingest_audit VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                    (run_id, source, v["make"], v["model"], year, len(rows), ins, upd, same))
                    log.info("%-10s %s %s %d fetched=%d inserted=%d updated=%d unchanged=%d",
                             source, v["make"], v["model"], year, len(rows), ins, upd, same)
                    time.sleep(0.5)

if __name__ == "__main__":
    try:
        run()
    except Exception:
        log.exception("ingestion failed"); sys.exit(1)
