"""ENR-2 (requirements/51): generate pgvector embeddings for every canonical
`knowledge.misconception` row and every `pedagogy.taxonomy_node` row (Concept/Skill/
Technique/Subconcept/Domain), then precompute top-k nearest-neighbor similarity pairs
for each. This is the real, direct fix for "no similarity search happening in the graph
at all" — it is a distinct, later-stage fix from ENR-1 Phase A's exact-text dedup
(which only caught 12.7% of duplicate misconceptions); this catches semantically related
but textually different content too (e.g. "Misapplication of Pythagorean theorem" vs.
"Misunderstanding Pythagorean theorem application" — confirmed live as a real pair in the
corpus during requirements/51's root-cause analysis).

Uses the project's existing OpenAI embedding convention (text-embedding-3-small, 1536
dimensions, confirmed live via `mathbank_rest.artifact_runtime.embedding_profile()`), but
calls the API in large batches (up to 500 inputs per call, confirmed live at ~500
embeddings/1.4s) rather than one string at a time — the existing `_openai_embedding()`
helper in artifact_runtime.py only supports one string per call, which would need ~77,000
HTTP round trips for this corpus; batching cuts that to well under 200 calls.

Bulk-insert pattern follows backfill_misconception_catalog.py's established, measured-fast
approach: deterministic no-RETURNING-needed writes, multi-row VALUES per batch.

Similarity pairs are computed entirely inside Postgres via pgvector's cosine-distance
operator (schema-qualified per GOTCHAS.md §15 — Neon's neondb_owner has an empty
search_path, so bare `vector`/`<=>` fail even though the extension is installed), keeping
only the top-K (default 8) neighbors per row above a minimum similarity threshold (default
0.80) — a full top-K self-join over ~77K rows is a few seconds of Postgres compute, not
something that needs an external clustering library.

Idempotent: re-running regenerates embeddings only for rows that don't have one yet
(`--force` recomputes everything), and similarity pairs are fully replaced (not
incrementally patched) on every run of the similarity step, which is cheap at this scale.

`--source s3vectors` (requirement 71 WP2) reads the vectors from S3 Vectors through the vector
adapter instead of pgvector: the misconception and taxonomy-node vectors are fetched with
`keys()` + `get`, each one is used as a query (`bulk_query`, engine auto: Bodo when installed,
boto3 otherwise; top-k + 1, the vector itself dropped, rank = ANN order, similarity >= 0.80,
taxonomy neighbours within the same node_type) and the same Postgres similarity tables are
truncated and reloaded in one transaction. Embedding generation is skipped in that mode: the
vector sync worker (`mathbank_rest.vector_sync`) keeps the S3 Vectors indexes current.
`--dry-run` (s3vectors only) computes the pairs and prints their counts without touching Postgres.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import time
from collections.abc import Iterator, Sequence

import numpy as np
from sqlalchemy import text

from mathbank_rest.artifact_runtime import embedding_profile
from mathbank_rest.db.postgres import engine
from mathbank_rest.runtime_ai import speech_client
from mathbank_rest.vector_bulk import Engine, bulk_query
from mathbank_rest.vector_catalog import Family
from mathbank_rest.vector_store import (
    S3VectorsStore,
    VectorHit,
    VectorStore,
    get_vector_store,
    uses_s3_vectors,
    vf,
)

BATCH_SIZE = 500
TOP_K = 8
MIN_SIMILARITY = 0.80


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _embed_batch(client, model: str, dimensions: int, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=model, input=texts, dimensions=dimensions)
    return [row.embedding for row in response.data]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def embed_misconceptions(force: bool, limit: int | None = None) -> dict:
    profile = embedding_profile()
    client = speech_client()
    with engine.connect() as conn:
        where = "" if force else "WHERE me.misconception_id IS NULL"
        limit_sql = f"LIMIT {int(limit)}" if limit else ""
        rows = conn.execute(
            text(f"""
            SELECT m.misconception_id::text AS id,
                   coalesce(m.description,'') || ' ' || coalesce(m.symptom,'') || ' '
                   || coalesce(m.why_wrong,'') || ' ' || coalesce(m.correct_model,'') AS source_text
            FROM knowledge.misconception m
            LEFT JOIN knowledge.misconception_embedding me ON me.misconception_id = m.misconception_id
            {where}
            {limit_sql}
        """)
        ).mappings().all()
    print(f"misconceptions needing embeddings: {len(rows)}")
    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        texts = [r["source_text"][:8000] for r in batch]
        vectors = _embed_batch(client, profile["model"], profile["dimensions"], texts)
        values_sql, params = [], {}
        for i, (row, vec) in enumerate(zip(batch, vectors)):
            values_sql.append(
                f"(CAST(:id_{i} AS uuid), :model_{i}, :dim_{i}, :sha_{i}, CAST(:vec_{i} AS public.vector(1536)))"
            )
            params |= {
                f"id_{i}": row["id"],
                f"model_{i}": profile["model"],
                f"dim_{i}": profile["dimensions"],
                f"sha_{i}": _sha256(row["source_text"]),
                f"vec_{i}": _vector_literal(vec),
            }
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                INSERT INTO knowledge.misconception_embedding
                    (misconception_id, model, dimensions, source_text_sha256, embedding)
                VALUES {", ".join(values_sql)}
                ON CONFLICT (misconception_id) DO UPDATE SET
                    model = EXCLUDED.model, dimensions = EXCLUDED.dimensions,
                    source_text_sha256 = EXCLUDED.source_text_sha256,
                    embedding = EXCLUDED.embedding, generated_at = now()
            """),
                params,
            )
        inserted += len(batch)
        print(f"  embedded {inserted}/{len(rows)} misconceptions")
    return {"embedded": inserted}


def embed_taxonomy_nodes(force: bool, limit: int | None = None) -> dict:
    profile = embedding_profile()
    client = speech_client()
    with engine.connect() as conn:
        where = "" if force else "WHERE te.taxonomy_node_id IS NULL"
        limit_sql = f"LIMIT {int(limit)}" if limit else ""
        rows = conn.execute(
            text(f"""
            SELECT t.taxonomy_node_id AS id,
                   coalesce(t.name,'') || ' ' || coalesce(t.description,'') AS source_text
            FROM pedagogy.taxonomy_node t
            LEFT JOIN pedagogy.taxonomy_node_embedding te ON te.taxonomy_node_id = t.taxonomy_node_id
            {where}
            {limit_sql}
        """)
        ).mappings().all()
    print(f"taxonomy_nodes needing embeddings: {len(rows)}")
    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        texts = [r["source_text"][:8000] or "untitled" for r in batch]
        vectors = _embed_batch(client, profile["model"], profile["dimensions"], texts)
        values_sql, params = [], {}
        for i, (row, vec) in enumerate(zip(batch, vectors)):
            values_sql.append(
                f"(:id_{i}, :model_{i}, :dim_{i}, :sha_{i}, CAST(:vec_{i} AS public.vector(1536)))"
            )
            params |= {
                f"id_{i}": row["id"],
                f"model_{i}": profile["model"],
                f"dim_{i}": profile["dimensions"],
                f"sha_{i}": _sha256(row["source_text"]),
                f"vec_{i}": _vector_literal(vec),
            }
        with engine.begin() as conn:
            conn.execute(
                text(f"""
                INSERT INTO pedagogy.taxonomy_node_embedding
                    (taxonomy_node_id, model, dimensions, source_text_sha256, embedding)
                VALUES {", ".join(values_sql)}
                ON CONFLICT (taxonomy_node_id) DO UPDATE SET
                    model = EXCLUDED.model, dimensions = EXCLUDED.dimensions,
                    source_text_sha256 = EXCLUDED.source_text_sha256,
                    embedding = EXCLUDED.embedding, generated_at = now()
            """),
                params,
            )
        inserted += len(batch)
        print(f"  embedded {inserted}/{len(rows)} taxonomy_nodes")
    return {"embedded": inserted}


def compute_misconception_similarity() -> dict:
    # Index-assisted top-K per row via LATERAL + ORDER BY ... LIMIT, which pgvector's HNSW
    # index can serve directly — NOT a full self-join (70,018 rows would be ~4.9 billion
    # pairs without this, impractical). Each outer row does one ANN lookup for its own
    # nearest neighbors instead of being compared against every other row.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE knowledge.misconception_similarity"))
        conn.execute(
            text("""
            INSERT INTO knowledge.misconception_similarity
                (misconception_id_a, misconception_id_b, similarity, rank)
            SELECT a.misconception_id, nn.misconception_id, nn.similarity, nn.rnk
            FROM knowledge.misconception_embedding a
            CROSS JOIN LATERAL (
                SELECT b.misconception_id,
                       1 - (a.embedding OPERATOR(public.<=>) b.embedding) AS similarity,
                       row_number() OVER (ORDER BY a.embedding OPERATOR(public.<=>) b.embedding) AS rnk
                FROM knowledge.misconception_embedding b
                WHERE b.misconception_id <> a.misconception_id
                ORDER BY a.embedding OPERATOR(public.<=>) b.embedding
                LIMIT :top_k
            ) nn
            WHERE nn.similarity >= :min_sim
        """),
            {"top_k": TOP_K, "min_sim": MIN_SIMILARITY},
        )
        count = conn.execute(text("SELECT count(*) FROM knowledge.misconception_similarity")).scalar()
    return {"pairs": count}


def compute_taxonomy_node_similarity() -> dict:
    # Same index-assisted LATERAL pattern as misconceptions, additionally scoped to same
    # node_type (comparing a Concept against a Technique by embedding distance is not a
    # meaningful "similar node" signal even if the vectors happen to be close).
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE pedagogy.taxonomy_node_similarity"))
        conn.execute(
            text("""
            INSERT INTO pedagogy.taxonomy_node_similarity
                (taxonomy_node_id_a, taxonomy_node_id_b, similarity, rank)
            SELECT a.taxonomy_node_id, nn.taxonomy_node_id, nn.similarity, nn.rnk
            FROM pedagogy.taxonomy_node_embedding a
            JOIN pedagogy.taxonomy_node tna ON tna.taxonomy_node_id = a.taxonomy_node_id
            CROSS JOIN LATERAL (
                SELECT b.taxonomy_node_id,
                       1 - (a.embedding OPERATOR(public.<=>) b.embedding) AS similarity,
                       row_number() OVER (ORDER BY a.embedding OPERATOR(public.<=>) b.embedding) AS rnk
                FROM pedagogy.taxonomy_node_embedding b
                JOIN pedagogy.taxonomy_node tnb ON tnb.taxonomy_node_id = b.taxonomy_node_id
                WHERE b.taxonomy_node_id <> a.taxonomy_node_id AND tnb.node_type = tna.node_type
                ORDER BY a.embedding OPERATOR(public.<=>) b.embedding
                LIMIT :top_k
            ) nn
            WHERE nn.similarity >= :min_sim
        """),
            {"top_k": TOP_K, "min_sim": MIN_SIMILARITY},
        )
        count = conn.execute(text("SELECT count(*) FROM pedagogy.taxonomy_node_similarity")).scalar()
    return {"pairs": count}


# ---------------------------------------------------------------- S3 Vectors source (--source s3vectors)

QUERY_BATCH = 2000
FETCH_WORKERS = 8
SimilarityRow = tuple[str, str, float, int]


def neighbours_from_hits(key: str, hits: Sequence[VectorHit], *, top_k: int = TOP_K,
                         min_similarity: float = MIN_SIMILARITY) -> list[SimilarityRow]:
    """Pure: (key, neighbour, similarity, rank) rows from one query's ANN hits.

    Same semantics as the pgvector LATERAL query: the vector itself is dropped, rank is the position among the first
    `top_k` remaining neighbours (1 = nearest), and only neighbours with similarity >= `min_similarity` are kept (a
    neighbour below the threshold still consumes its rank)."""
    rows: list[SimilarityRow] = []
    rank = 0
    for hit in hits:
        if hit.key == key:
            continue
        rank += 1
        if rank > top_k:
            break
        if hit.similarity >= min_similarity:
            rows.append((key, hit.key, float(hit.similarity), rank))
    return rows


def query_groups(family: Family, metas: Sequence[dict]) -> Iterator[tuple[dict | None, list[int]]]:
    """Pure: (filter, indexes of the vectors to query) groups. Misconceptions are one unfiltered group; taxonomy nodes are
    grouped by node_type (neighbours only within the same type) and only nodes that still exist (lifecycle ACTIVE, node_type
    set) take part, like the INNER JOINs of the pgvector query."""
    if family != Family.TAXONOMY_NODE:
        yield None, list(range(len(metas)))
        return
    by_type: dict[str, list[int]] = {}
    for i, meta in enumerate(metas):
        if meta.get("lifecycle") == "ACTIVE" and meta.get("node_type"):
            by_type.setdefault(meta["node_type"], []).append(i)
    for node_type, idx in sorted(by_type.items()):
        yield vf.and_(vf.eq("node_type", node_type), vf.eq("lifecycle", "ACTIVE")), idx


def similarity_rows(family: Family, keys: Sequence[str], matrix: np.ndarray, metas: Sequence[dict], store: VectorStore,
                    engine_name: Engine = "auto", batch: int = QUERY_BATCH) -> list[SimilarityRow]:
    """Top-K neighbour rows for every vector of `family` through `bulk_query`; vectors are queried in batches."""
    rows: list[SimilarityRow] = []
    for flt, idx in query_groups(family, metas):
        for start in range(0, len(idx), batch):
            part = idx[start:start + batch]
            answers = bulk_query(family, [matrix[i].tolist() for i in part], top_k=TOP_K + 1, filter=flt, engine=engine_name, store=store)
            for i, hits in zip(part, answers, strict=True):
                rows.extend(neighbours_from_hits(keys[i], hits))
            print(f"  {family.value}: queried {min(start + batch, len(idx))}/{len(idx)}")
    return rows


def fetch_vectors(store: VectorStore, family: Family, workers: int = FETCH_WORKERS) -> tuple[list[str], np.ndarray, list[dict]]:
    """Every vector of the family through the adapter (`keys()` + `get`), as a float32 matrix."""
    keys = sorted(store.keys(family))
    chunks = [keys[i:i + 100] for i in range(0, len(keys), 100)]
    found: dict[str, tuple[np.ndarray, dict]] = {}
    with cf.ThreadPoolExecutor(max(1, min(workers, len(chunks)))) as ex:
        for items in ex.map(lambda c: store.get(family, c, with_data=True), chunks):
            found.update({it.key: (np.asarray(it.vector, np.float32), dict(it.metadata)) for it in items if it.vector is not None})
    keys = [k for k in keys if k in found]
    matrix = np.vstack([found[k][0] for k in keys]) if keys else np.zeros((0, 1536), np.float32)
    return keys, matrix, [found[k][1] for k in keys]


def _s3_store() -> VectorStore:
    return get_vector_store() if uses_s3_vectors() else S3VectorsStore()


def _replace_similarity(table: str, columns: tuple[str, str], rows: Sequence[SimilarityRow], cast: str) -> int:
    a, b = columns
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table}"))
        for start in range(0, len(rows), 5000):
            conn.execute(
                text(f"INSERT INTO {table} ({a}, {b}, similarity, rank) VALUES "
                     f"(CAST(:a AS {cast}), CAST(:b AS {cast}), :sim, :rnk)"),
                [{"a": r[0], "b": r[1], "sim": r[2], "rnk": r[3]} for r in rows[start:start + 5000]],
            )
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def compute_similarity_from_s3vectors(family: Family, engine_name: Engine = "auto", dry_run: bool = False,
                                      limit: int | None = None) -> dict:
    store = _s3_store()
    keys, matrix, metas = fetch_vectors(store, family)
    print(f"{family.value}: {len(keys)} vectors read from S3 Vectors")
    if limit:
        keys, matrix, metas = keys[:limit], matrix[:limit], metas[:limit]
    rows = similarity_rows(family, keys, matrix, metas, store, engine_name)
    if dry_run:
        return {"pairs": len(rows), "dry_run": True}
    if family == Family.MISCONCEPTION:
        pairs = _replace_similarity("knowledge.misconception_similarity", ("misconception_id_a", "misconception_id_b"), rows, "uuid")
    else:
        pairs = _replace_similarity("pedagogy.taxonomy_node_similarity", ("taxonomy_node_id_a", "taxonomy_node_id_b"), rows, "text")
    return {"pairs": pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Recompute embeddings for rows that already have one.")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation, only (re)compute similarity pairs.")
    parser.add_argument("--limit", type=int, default=None, help="Only embed this many rows per table (testing).")
    parser.add_argument("--source", choices=["pgvector", "s3vectors"], default="pgvector",
                        help="Where the vectors come from (s3vectors: read through the vector adapter; embedding generation is skipped).")
    parser.add_argument("--engine", choices=["auto", "boto3", "bodo"], default="auto", help="Bulk query engine for --source s3vectors.")
    parser.add_argument("--dry-run", action="store_true", help="With --source s3vectors: compute the pairs, print counts, do not touch Postgres.")
    args = parser.parse_args()
    if args.source == "pgvector" and args.dry_run:
        parser.error("--dry-run needs --source s3vectors")
    if args.source == "s3vectors" and args.limit and not args.dry_run:
        parser.error("--limit with --source s3vectors needs --dry-run (a partial rebuild would truncate the similarity tables)")

    t0 = time.time()
    if args.source == "s3vectors":
        if args.force:
            parser.error("--force applies to pgvector embeddings only; the vector sync worker maintains the S3 Vectors indexes")
        for family in (Family.MISCONCEPTION, Family.TAXONOMY_NODE):
            print(compute_similarity_from_s3vectors(family, args.engine, args.dry_run, args.limit))
        print(f"done in {time.time() - t0:.1f}s")
        return
    if not args.skip_embed:
        print(embed_misconceptions(args.force, args.limit))
        print(embed_taxonomy_nodes(args.force, args.limit))
    print(compute_misconception_similarity())
    print(compute_taxonomy_node_similarity())
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
