"""
Semantic search over complaint narratives.

  python rag/search.py "car slams on the brakes on the highway for no reason" --make TESLA -k 5
"""
import argparse

from psycopg import sql

from rag_common import connect, get_backend


def search(cur, backend, query_vec, k=5, make=None, model=None, year=None, exclude_odi=None):
    """Top-k distinct complaints by cosine similarity, optionally filtered to a vehicle."""
    filters = [sql.SQL("embed_model = {}").format(sql.Literal(backend.name))]
    params = []
    for col, val in (("make", make), ("model", model), ("model_year", year)):
        if val is not None:
            filters.append(sql.SQL("{} = %s").format(sql.Identifier(col)))
            params.append(val)
    if exclude_odi is not None:
        filters.append(sql.SQL("odi_number <> %s"))
        params.append(exclude_odi)
    q = sql.SQL("""
        SELECT odi_number, make, model, model_year, component_groups, chunk_text,
               1 - (embedding <=> %s) AS similarity
        FROM rag.complaint_chunks
        WHERE {where}
        ORDER BY embedding <=> %s
        LIMIT %s
    """).format(where=sql.SQL(" AND ").join(filters))
    cur.execute(q, [query_vec, *params, query_vec, k * 4])
    seen, out = set(), []
    for row in cur.fetchall():  # a complaint can have several chunks: keep its best one
        if row[0] in seen:
            continue
        seen.add(row[0])
        out.append(row)
        if len(out) == k:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--make")
    ap.add_argument("--model")
    ap.add_argument("--year", type=int)
    ap.add_argument("--backend", choices=["minilm", "hash"], default="minilm")
    args = ap.parse_args()

    backend = get_backend(args.backend)
    vec = backend.encode([args.query])[0]
    with connect() as conn, conn.cursor() as cur:
        rows = search(cur, backend, vec, args.k, args.make and args.make.upper(),
                      args.model and args.model.upper(), args.year)
    for odi, make, model, year, groups, text, sim in rows:
        print(f"[{sim:.3f}] ODI {odi} | {make} {model} {year} | {', '.join(groups)}")
        print(f"        {text[:220]}{'...' if len(text) > 220 else ''}")


if __name__ == "__main__":
    main()
