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
"""
from __future__ import annotations

import argparse
import hashlib
import time

from sqlalchemy import text

from mathbank_rest.artifact_runtime import embedding_profile
from mathbank_rest.db.postgres import engine
from mathbank_rest.runtime_ai import speech_client

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Recompute embeddings for rows that already have one.")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation, only (re)compute similarity pairs.")
    parser.add_argument("--limit", type=int, default=None, help="Only embed this many rows per table (testing).")
    args = parser.parse_args()

    t0 = time.time()
    if not args.skip_embed:
        print(embed_misconceptions(args.force, args.limit))
        print(embed_taxonomy_nodes(args.force, args.limit))
    print(compute_misconception_similarity())
    print(compute_taxonomy_node_similarity())
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
