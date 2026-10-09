"""
Embed complaint narratives from silver.int_complaints into rag.complaint_chunks.

Incremental and idempotent: a complaint is (re-)embedded only when its source hash
(description + component groups) changed since the last run for that model.
"""
import argparse
import time

from psycopg import sql

from rag_common import chunk_text, connect, get_backend, source_hash

SOURCE = """
SELECT odi_number, make, model, model_year, component_groups, description
FROM silver.int_complaints
WHERE description IS NOT NULL AND btrim(description) <> ''
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["minilm", "hash"], default="minilm")
    ap.add_argument("--limit", type=int, default=0, help="dev only: embed at most N complaints")
    args = ap.parse_args()

    t0 = time.time()
    backend = get_backend(args.backend)
    model_lit = sql.Literal(backend.name)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SOURCE)
        complaints = cur.fetchall()
        cur.execute(sql.SQL("""
            SELECT DISTINCT odi_number, make, model, model_year, source_hash
            FROM rag.complaint_chunks WHERE embed_model = {}""").format(model_lit))
        existing = {(o, m, mo, y): h for o, m, mo, y, h in cur.fetchall()}

        todo = []
        for odi, make, model, year, groups, desc in complaints:
            h = source_hash(desc, groups)
            if existing.get((odi, make, model, year)) != h:
                todo.append((odi, make, model, year, groups, desc, h))
        if args.limit:
            todo = todo[: args.limit]

        current = {(o, m, mo, y) for o, m, mo, y, *_ in complaints}
        stale = [k for k in existing if k not in current]

        rows = []
        for odi, make, model, year, groups, desc, h in todo:
            for n, chunk in enumerate(chunk_text(desc)):
                rows.append((odi, make, model, year, n, groups, chunk, h))

        vectors = backend.encode([r[6] for r in rows]) if rows else []
        with conn.transaction():
            for odi, make, model, year, *_ in todo:
                cur.execute(sql.SQL("""DELETE FROM rag.complaint_chunks
                    WHERE odi_number=%s AND make=%s AND model=%s AND model_year=%s AND embed_model={}""")
                    .format(model_lit), (odi, make, model, year))
            for odi, make, model, year in stale:
                cur.execute(sql.SQL("""DELETE FROM rag.complaint_chunks
                    WHERE odi_number=%s AND make=%s AND model=%s AND model_year=%s AND embed_model={}""")
                    .format(model_lit), (odi, make, model, year))
            cur.executemany(
                """INSERT INTO rag.complaint_chunks
                   (odi_number, make, model, model_year, chunk_no, embed_model, component_groups,
                    chunk_text, source_hash, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [(o, m, mo, y, n, backend.name, g, c, h, v)
                 for (o, m, mo, y, n, g, c, h), v in zip(rows, vectors)],
            )
        cur.execute(sql.SQL("SELECT count(*), count(DISTINCT odi_number) FROM rag.complaint_chunks WHERE embed_model = {}")
                    .format(model_lit))
        total_chunks, total_complaints = cur.fetchone()

    print(f"backend={backend.name} source_complaints={len(complaints)} embedded={len(todo)} "
          f"unchanged={len(complaints) - len(todo)} removed_stale={len(stale)} new_chunks={len(rows)} "
          f"table_chunks={total_chunks} table_complaints={total_complaints} seconds={time.time() - t0:.1f}")


if __name__ == "__main__":
    main()
