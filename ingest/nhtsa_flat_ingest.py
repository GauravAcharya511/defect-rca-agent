import csv, hashlib, io, json, logging, os, sys, uuid, zipfile
from collections import defaultdict
from pathlib import Path
import psycopg, requests
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"
CONFIG = ROOT / "config" / "vehicles.json"
DSN = os.getenv("PG_DSN", "postgresql://rca:rca@localhost:5433/rca")
FILES = [
    "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2020-2024.zip",
    "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2025-2026.zip",
]
FIELDS = [
    "CMPLID", "ODINO", "MFR_NAME", "MAKETXT", "MODELTXT", "YEARTXT", "CRASH", "FAILDATE", "FIRE",
    "INJURED", "DEATHS", "COMPDESC", "CITY", "STATE", "VIN", "DATEA", "LDATE", "MILES", "OCCURENCES",
    "CDESCR", "CMPL_TYPE", "POLICE_RPT_YN", "PURCH_DT", "ORIG_OWNER_YN", "ANTI_BRAKES_YN",
    "CRUISE_CONT_YN", "NUM_CYLS", "DRIVE_TRAIN", "FUEL_SYS", "FUEL_TYPE", "TRANS_TYPE", "VEH_SPEED",
    "DOT", "TIRE_SIZE", "LOC_OF_TIRE", "TIRE_FAIL_TYPE", "ORIG_EQUIP_YN", "MANUF_DT", "SEAT_TYPE",
    "RESTRAINT_TYPE", "DEALER_NAME", "DEALER_TEL", "DEALER_CITY", "DEALER_STATE", "DEALER_ZIP",
    "PROD_TYPE", "REPAIRED_YN", "MEDICAL_ATTN", "VEHICLES_TOWED_YN", "STATE_OF_INCIDENT",
    "VEHICLE_OPERATOR",
]
DROP = {"CITY", "VIN", "DEALER_TEL", "VEHICLE_OPERATOR"}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("nhtsa_flat_ingest")

UPSERT = """
INSERT INTO bronze.nhtsa_complaints_flat
    (odi_number, component, make, model, model_year, source_file, payload, payload_hash)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (odi_number, component, make, model, model_year) DO UPDATE
   SET payload = EXCLUDED.payload, payload_hash = EXCLUDED.payload_hash,
       source_file = EXCLUDED.source_file, updated_at = now()
 WHERE bronze.nhtsa_complaints_flat.payload_hash <> EXCLUDED.payload_hash
RETURNING (xmax = 0) AS inserted
"""

def download(url):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / url.rsplit("/", 1)[-1]
    if dest.exists():
        log.info("using cached %s (%.0f MB)", dest.name, dest.stat().st_size / 1e6)
        return dest
    log.info("downloading %s", url)
    tmp = dest.with_suffix(".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    log.info("saved %s (%.0f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest

def rows(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        with zf.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            for parts in csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(parts) < 12:
                    continue
                parts += [""] * (len(FIELDS) - len(parts))
                yield dict(zip(FIELDS, (p.strip() for p in parts)))

def payload_hash(p):
    return hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def run():
    wanted = {}
    for v in json.loads(CONFIG.read_text()):
        for y in v["years"]:
            wanted[(v["make"].upper(), v["model"].upper(), str(y))] = True
    run_id = uuid.uuid4()
    log.info("run_id=%s vehicle-years=%d", run_id, len(wanted))
    with psycopg.connect(DSN) as conn:
        for url in FILES:
            zip_path = download(url)
            stats = defaultdict(lambda: [0, 0, 0, 0])
            scanned = 0
            with conn.transaction(), conn.cursor() as cur:
                for rec in rows(zip_path):
                    scanned += 1
                    key = (rec["MAKETXT"].upper(), rec["MODELTXT"].upper(), rec["YEARTXT"])
                    if key not in wanted or not rec["ODINO"].isdigit():
                        continue
                    payload = {k: v for k, v in rec.items() if k not in DROP and v != ""}
                    component = rec["COMPDESC"] or "UNKNOWN"
                    cur.execute(UPSERT, (int(rec["ODINO"]), component, key[0], key[1], int(key[2]),
                                         zip_path.name, Jsonb(payload), payload_hash(payload)))
                    res = cur.fetchone()
                    s = stats[key]
                    s[0] += 1
                    if res is None: s[3] += 1
                    elif res[0]: s[1] += 1
                    else: s[2] += 1
                for (make, model, year) in wanted:
                    f, i, u, n = stats.get((make, model, year), (0, 0, 0, 0))
                    cur.execute("INSERT INTO bronze.ingest_audit VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (run_id, f"complaints_flat:{zip_path.name}", make, model, int(year), f, i, u, n))
            log.info("%s: scanned %d rows", zip_path.name, scanned)
            for (make, model, year), (f, i, u, n) in sorted(stats.items()):
                log.info("  %s %s %s matched=%d inserted=%d updated=%d unchanged=%d", make, model, year, f, i, u, n)

if __name__ == "__main__":
    try:
        run()
    except Exception:
        log.exception("flat-file ingestion failed"); sys.exit(1)
