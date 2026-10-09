"""
Retrieval quality check, using NHTSA's own component tags as relevance labels.

For a fixed sample of complaints, use each complaint's narrative as the query, retrieve the
k most similar OTHER complaints, and count a neighbour as relevant when it shares at least
one component group with the query. Compared against the rate a random pick would achieve.

  precision@k  share of retrieved neighbours that share a component group
  random@k     expected precision if neighbours were picked at random from the corpus
  lift         precision@k / random@k
  hit@k        share of queries with at least one relevant neighbour
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from psycopg import sql

from rag_common import connect, get_backend
from search import search

IGNORE = {"UNKNOWN OR OTHER"}  # not a real failure mode: matching on it proves nothing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["minilm", "hash"], default="minilm")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--sample", type=int, default=500)
    ap.add_argument("--seed", default="rca")
    args = ap.parse_args()

    backend = get_backend(args.backend)
    lit = sql.Literal(backend.name)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("""SELECT odi_number, max(component_groups::text)::text[]
                               FROM rag.complaint_chunks WHERE embed_model = {} AND chunk_no = 0
                               GROUP BY odi_number""").format(lit))
        labels = {odi: set(g) - IGNORE for odi, g in cur.fetchall()}
        corpus = [g for g in labels.values() if g]

        cur.execute(sql.SQL("""SELECT odi_number, embedding FROM rag.complaint_chunks
                               WHERE embed_model = {} AND chunk_no = 0
                               ORDER BY md5(odi_number::text || %s)""").format(lit), (args.seed,))
        queries, seen = [], set()
        for odi, emb in cur.fetchall():
            if odi in seen or not labels.get(odi):
                continue
            seen.add(odi)
            queries.append((odi, emb))
            if len(queries) == args.sample:
                break

        precisions, randoms, hits, latencies = [], [], [], []
        for odi, emb in queries:
            q_groups = labels[odi]
            t = time.perf_counter()
            neighbours = search(cur, backend, emb, args.k, exclude_odi=odi)
            latencies.append((time.perf_counter() - t) * 1000)
            rel = [bool(labels.get(n[0], set()) & q_groups) for n in neighbours]
            precisions.append(sum(rel) / args.k)
            hits.append(any(rel))
            randoms.append(sum(1 for g in corpus if g & q_groups) / len(corpus))

    p, r = statistics.mean(precisions), statistics.mean(randoms)
    lat = sorted(latencies)
    result = {
        "backend": backend.name, "k": args.k, "queries": len(queries), "corpus_complaints": len(corpus),
        f"precision@{args.k}": round(p, 4), f"random@{args.k}": round(r, 4), "lift": round(p / r, 2),
        f"hit@{args.k}": round(statistics.mean(hits), 4),
        "latency_ms_p50": round(lat[len(lat) // 2], 2), "latency_ms_p95": round(lat[int(len(lat) * 0.95)], 2),
    }
    out = Path(__file__).resolve().parent.parent / "eval" / "results" / f"retrieval_{args.backend}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    for key, val in result.items():
        print(f"{key:>18}: {val}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
