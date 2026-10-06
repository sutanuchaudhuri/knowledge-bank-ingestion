"""Phase 5 (v2 pack): pgvector representations for solution steps, published learning items
and taxonomy nodes (concept-level similarity).

Extends the existing search.representation -> search.chunk -> search.embedding pipeline
(embed_corpus.py) instead of rebuilding it. Every chunk carries canonical taxonomy IDs
as indexed columns plus a metadata document, so retrieval can hard-filter before ranking
(runtime_extension/07_VECTOR_METADATA_AND_RAG.md).

Only `PUBLISHED` steps and learning items that are APPROVED, student-visible and no-proof
are represented; every `pedagogy.taxonomy_node` (DOMAIN/CONCEPT/SUBCONCEPT/SKILL/TECHNIQUE) gets one
TAXONOMY_NODE representation rendered from its name, parent path and taxonomy-edge neighbours.
Anything that stops being eligible has its representation SUPERSEDED.
Re-running without content changes performs no new embeddings.

Usage (remote: PG_ENV_FILE=../mathbank-graph/remote.env):
    python etl/embed_textbook_steps.py build     # representations + chunks only (no paid calls)
    python etl/embed_textbook_steps.py backfill  # build, then embed pending step/item/taxonomy chunks
    python etl/embed_textbook_steps.py status    # reconcile eligible rows vs ACTIVE embeddings
    python etl/embed_textbook_steps.py papers    # print --paper args for embed_corpus.py (textbook problems)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embed_corpus  # noqa: E402

PROFILE_NAME = "pedagogy_step_v2"
PROFILE_VERSION = 1
STEP_KIND = "SOLUTION_STEP"
ITEM_QUESTION_KIND = "LEARNING_ITEM_QUESTION"
ITEM_SIGNATURE_KIND = "LEARNING_ITEM_SKILL_SIGNATURE"
TAXONOMY_KIND = "TAXONOMY_NODE"
KINDS = [STEP_KIND, ITEM_QUESTION_KIND, ITEM_SIGNATURE_KIND, TAXONOMY_KIND]
ENTITY_TYPE = {STEP_KIND: "SOLUTION_STEP", ITEM_QUESTION_KIND: "LEARNING_ITEM", ITEM_SIGNATURE_KIND: "LEARNING_ITEM",
               TAXONOMY_KIND: "TAXONOMY_NODE"}
# Imported descriptions that only record provenance carry no meaning and would add noise to the vector.
BOILERPLATE_DESCRIPTION = re.compile(
    r"^(?:(?:skill|technique|concept) from existing enrichment"
    r"|method/subtopic from chapter \d+"
    r"|canonical concept for prasolov chapter \d+"
    r"|canonical geometry domain"
    r"|skill inferred from ordered solution steps)\.?$", re.I)
MAX_NEIGHBOURS = 15
# Stable namespace: search.representation.source_entity_id is uuid but pedagogy IDs are text.
ENTITY_NAMESPACE = uuid.UUID("7d0c5f3e-5a0b-4f3e-9a63-0e8f2f1b6c11")


def surrogate_id(entity_type: str, entity_id: str) -> str:
    return str(uuid.uuid5(ENTITY_NAMESPACE, f"{entity_type}:{entity_id}"))


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StageRow:
    kind: str
    entity_id: str
    rendered_text: str
    problem_id: str | None
    solution_id: str | None
    solution_step_id: str | None
    learning_item_id: str | None
    skill_node_id: str | None
    subconcept_node_id: str | None
    concept_node_id: str | None
    metadata: dict

    @property
    def entity_type(self) -> str:
        return ENTITY_TYPE[self.kind]

    @property
    def source_entity_id(self) -> str:
        return surrogate_id(self.entity_type, self.entity_id)

    @property
    def content_hash(self) -> str:
        return sha256(self.rendered_text)


STEP_SQL = """
SELECT s.solution_step_id, s.solution_part_id, s.solution_id::text, s.problem_id::text,
       s.global_step_index, s.step_index_in_part, s.step_text, s.step_type, s.tutor_role,
       s.concept_node_id, s.subconcept_node_id, s.skill_node_id, s.skill_name,
       s.hint_level, s.is_checkpoint, s.publication_status, s.book_code,
       r.chapter_number, r.section_number, r.section_title,
       sub.name AS subconcept_name,
       coalesce((SELECT array_agg(t.slug ORDER BY t.slug)
                   FROM knowledge.problem_technique pt
                   JOIN knowledge.technique t USING (technique_id)
                  WHERE pt.problem_id = s.problem_id), '{}') AS technique_slugs,
       coalesce((SELECT array_agg(st.technique_node_id ORDER BY st.technique_node_id)
                   FROM pedagogy.solution_step_technique st
                  WHERE st.solution_step_id = s.solution_step_id
                    AND st.review_status = 'APPROVED'), '{}') AS step_technique_ids
  FROM pedagogy.solution_step s
  LEFT JOIN pedagogy.problem_source_ref r ON r.problem_id = s.problem_id
  LEFT JOIN pedagogy.taxonomy_node sub ON sub.taxonomy_node_id = s.subconcept_node_id
 WHERE s.publication_status = 'PUBLISHED'
 ORDER BY s.problem_id, s.global_step_index
"""

ITEM_SQL = """
SELECT li.learning_item_id, li.source_problem_id::text, li.transformed_form, li.transformation_type,
       li.target_concept_node_id, li.target_subconcept_node_id, li.target_skill_node_id,
       li.difficulty_direction, li.question_text, li.no_proof, li.review_status,
       li.student_visible, li.diagram_strategy, li.book_code,
       skill.name AS skill_name, sub.name AS subconcept_name,
       (SELECT a.solution_step_id FROM pedagogy.learning_item_step_anchor a
         WHERE a.learning_item_id = li.learning_item_id
         ORDER BY a.anchor_ordinal, a.solution_step_id LIMIT 1) AS anchor_step_id,
       r.chapter_number, r.section_number
  FROM pedagogy.learning_item li
  LEFT JOIN pedagogy.taxonomy_node skill ON skill.taxonomy_node_id = li.target_skill_node_id
  LEFT JOIN pedagogy.taxonomy_node sub ON sub.taxonomy_node_id = li.target_subconcept_node_id
  LEFT JOIN pedagogy.problem_source_ref r ON r.problem_id = li.source_problem_id
 WHERE li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof
 ORDER BY li.learning_item_id
"""


def step_rows(records: list[dict]) -> list[StageRow]:
    rows = []
    for s in records:
        label = s["skill_name"] or s["subconcept_name"] or ""
        rendered = f"[Solution step] {label}\n{s['step_text']}".strip()
        rows.append(StageRow(
            kind=STEP_KIND, entity_id=s["solution_step_id"], rendered_text=rendered,
            problem_id=s["problem_id"], solution_id=s["solution_id"],
            solution_step_id=s["solution_step_id"], learning_item_id=None,
            skill_node_id=s["skill_node_id"], subconcept_node_id=s["subconcept_node_id"],
            concept_node_id=s["concept_node_id"],
            metadata={
                "unit": STEP_KIND,
                "problem_id": s["problem_id"], "solution_id": s["solution_id"],
                "solution_part_id": s["solution_part_id"], "solution_step_id": s["solution_step_id"],
                "concept_id": s["concept_node_id"], "subconcept_id": s["subconcept_node_id"],
                "skill_id": s["skill_node_id"], "technique_ids": list(s["technique_slugs"] or []),
                # Step-level (migration 017); technique_ids above stays problem-level for compatibility.
                "step_technique_ids": list(s.get("step_technique_ids") or []),
                "step_type": s["step_type"], "tutor_role": s["tutor_role"],
                "hint_level": s["hint_level"], "is_checkpoint": bool(s["is_checkpoint"]),
                "global_step_index": s["global_step_index"],
                "source_book": s["book_code"], "chapter": s["chapter_number"],
                "section": s["section_number"], "publication_status": s["publication_status"],
            },
        ))
    return rows


def item_rows(records: list[dict]) -> list[StageRow]:
    rows = []
    for li in records:
        if not (li["review_status"] == "APPROVED" and li["student_visible"] and li["no_proof"]):
            continue
        metadata = {
            "source_problem_id": li["source_problem_id"], "solution_step_anchor_id": li["anchor_step_id"],
            "learning_item_type": li["transformed_form"], "transformation_type": li["transformation_type"],
            "target_concept_id": li["target_concept_node_id"],
            "target_skill_id": li["target_skill_node_id"], "target_subconcept_id": li["target_subconcept_node_id"],
            "difficulty": li["difficulty_direction"], "no_proof": True,
            "review_status": li["review_status"], "publication_status": "PUBLISHED",
            "diagram_strategy": li["diagram_strategy"], "source_book": li["book_code"],
            "chapter": li["chapter_number"], "section": li["section_number"],
        }
        signature = " | ".join(filter(None, [
            li["transformation_type"], li["transformed_form"], li["skill_name"], li["subconcept_name"],
        ]))
        for kind, rendered in (
            (ITEM_QUESTION_KIND, f"[Learning item] {li['question_text']}".strip()),
            (ITEM_SIGNATURE_KIND, f"[Skill signature] {signature}".strip()),
        ):
            rows.append(StageRow(
                kind=kind, entity_id=li["learning_item_id"], rendered_text=rendered,
                problem_id=li["source_problem_id"], solution_id=None, solution_step_id=None,
                learning_item_id=li["learning_item_id"], skill_node_id=li["target_skill_node_id"],
                subconcept_node_id=li["target_subconcept_node_id"],
                concept_node_id=li["target_concept_node_id"],
                metadata={"unit": kind, **metadata},
            ))
    return rows


TAXONOMY_NODE_SQL = """
SELECT n.taxonomy_node_id, n.node_type, n.name, n.parent_node_id, n.chapter_number, n.section_number,
       n.description, n.concept_id::text, n.skill_id::text, n.technique_id::text, cp.book_code
  FROM pedagogy.taxonomy_node n
  JOIN ingest.content_package cp USING (content_package_id)
 ORDER BY n.taxonomy_node_id
"""

TAXONOMY_EDGE_SQL = """
SELECT from_node_id, to_node_id, relationship_type FROM pedagogy.taxonomy_edge
 ORDER BY from_node_id, to_node_id, relationship_type
"""


def _names(nodes: dict, ids) -> str:
    names = sorted({nodes[i]["name"] for i in ids if i in nodes})
    extra = len(names) - MAX_NEIGHBOURS
    return "; ".join(names[:MAX_NEIGHBOURS]) + (f"; and {extra} more" if extra > 0 else "")


def taxonomy_rows(nodes: list[dict], edges: list[dict]) -> list[StageRow]:
    by_id = {n["taxonomy_node_id"]: n for n in nodes}
    children: dict[str, set] = {}
    part_of: dict[str, set] = {}      # SKILL -> SUBCONCEPTs (and any other PART_OF targets)
    has_parts: dict[str, set] = {}    # reverse of PART_OF
    supports: dict[str, set] = {}     # TECHNIQUE -> SUBCONCEPTs
    supported_by: dict[str, set] = {}
    for n in nodes:
        if n["parent_node_id"]:
            children.setdefault(n["parent_node_id"], set()).add(n["taxonomy_node_id"])
    for e in edges:
        a, b, rel = e["from_node_id"], e["to_node_id"], e["relationship_type"]
        if rel == "PART_OF":
            part_of.setdefault(a, set()).add(b)
            has_parts.setdefault(b, set()).add(a)
        elif rel == "SUPPORTS":
            supports.setdefault(a, set()).add(b)
            supported_by.setdefault(b, set()).add(a)

    rows = []
    for n in nodes:
        node_id, node_type = n["taxonomy_node_id"], n["node_type"]
        path, cursor, seen = [], n["parent_node_id"], {node_id}
        while cursor and cursor in by_id and cursor not in seen:
            seen.add(cursor)
            path.append(by_id[cursor]["name"])
            cursor = by_id[cursor]["parent_node_id"]
        lines = [f"[Taxonomy {node_type.lower()}] {n['name']}"]
        if path:
            lines.append("Within: " + " > ".join(reversed(path)))
        if n["chapter_number"] is not None:
            section = f", section {n['section_number']}" if n["section_number"] else ""
            lines.append(f"Chapter {n['chapter_number']}{section}")
        description = (n["description"] or "").strip()
        if description and not BOILERPLATE_DESCRIPTION.match(description):
            lines.append(description)
        child_ids = children.get(node_id, set())
        part_ids = has_parts.get(node_id, set()) - child_ids
        neighbour_lines = [
            ("Contains", child_ids),
            ("Skills", {i for i in part_ids if by_id.get(i, {}).get("node_type") == "SKILL"}),
            ("Has parts", {i for i in part_ids if by_id.get(i, {}).get("node_type") != "SKILL"}),
            ("Techniques", supported_by.get(node_id, set())),
            ("Used in", part_of.get(node_id, set()) - {n["parent_node_id"]}),
            ("Supports", supports.get(node_id, set())),
        ]
        lines += [f"{label}: {_names(by_id, ids)}" for label, ids in neighbour_lines if ids]

        parent = by_id.get(n["parent_node_id"]) if n["parent_node_id"] else None
        concept = node_id if node_type == "CONCEPT" else (
            parent["taxonomy_node_id"] if node_type == "SUBCONCEPT" and parent and parent["node_type"] == "CONCEPT"
            else None)
        rows.append(StageRow(
            kind=TAXONOMY_KIND, entity_id=node_id, rendered_text="\n".join(lines),
            problem_id=None, solution_id=None, solution_step_id=None, learning_item_id=None,
            skill_node_id=node_id if node_type == "SKILL" else None,
            subconcept_node_id=node_id if node_type == "SUBCONCEPT" else None,
            concept_node_id=concept,
            metadata={
                "unit": TAXONOMY_KIND, "taxonomy_node_id": node_id, "node_type": node_type,
                "name": n["name"], "parent_node_id": n["parent_node_id"],
                "chapter": n["chapter_number"], "section": n["section_number"],
                "related_node_ids": sorted(
                    child_ids | has_parts.get(node_id, set()) | part_of.get(node_id, set())
                    | supports.get(node_id, set()) | supported_by.get(node_id, set())),
                "core_concept_id": n["concept_id"], "core_skill_id": n["skill_id"],
                "core_technique_id": n["technique_id"], "source_book": n["book_code"],
            },
        ))
    return rows


def _fetch(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    columns = [d.name for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def ensure_profile(cur) -> str:
    cur.execute(
        "INSERT INTO search.preprocessing_profile (name, version, configuration) VALUES (%s, %s, '{}'::jsonb) "
        "ON CONFLICT (name, version) DO NOTHING", (PROFILE_NAME, PROFILE_VERSION))
    cur.execute("SELECT preprocessing_profile_id FROM search.preprocessing_profile WHERE name=%s AND version=%s",
                (PROFILE_NAME, PROFILE_VERSION))
    return str(cur.fetchone()[0])


def build(cur, profile_id: str) -> dict:
    rows = (step_rows(_fetch(cur, STEP_SQL)) + item_rows(_fetch(cur, ITEM_SQL))
            + taxonomy_rows(_fetch(cur, TAXONOMY_NODE_SQL), _fetch(cur, TAXONOMY_EDGE_SQL)))
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS pedagogy_vector_stage (
            entity_type text, source_entity_id uuid, kind text, rendered_text text, content_hash text,
            token_count int, char_count int, problem_id uuid, solution_id uuid, solution_step_id text,
            learning_item_id text, skill_node_id text, subconcept_node_id text, concept_node_id text,
            metadata jsonb) ON COMMIT DROP""")
    cur.execute("TRUNCATE pedagogy_vector_stage")
    with cur.copy("COPY pedagogy_vector_stage FROM STDIN") as copy:
        for r in rows:
            copy.write_row((
                r.entity_type, r.source_entity_id, r.kind, r.rendered_text, r.content_hash,
                len(embed_corpus._encoding.encode(r.rendered_text)), len(r.rendered_text),
                r.problem_id, r.solution_id, r.solution_step_id, r.learning_item_id,
                r.skill_node_id, r.subconcept_node_id, r.concept_node_id, json.dumps(r.metadata, sort_keys=True),
            ))
    cur.execute("""
        UPDATE search.representation r SET status='SUPERSEDED'
         WHERE r.preprocessing_profile_id=%s AND r.representation_kind=ANY(%s) AND r.status='ACTIVE'
           AND NOT EXISTS (SELECT 1 FROM pedagogy_vector_stage s
                            WHERE s.entity_type=r.source_entity_type AND s.source_entity_id=r.source_entity_id
                              AND s.kind=r.representation_kind AND s.content_hash=r.content_hash)""",
                (profile_id, KINDS))
    superseded = cur.rowcount
    cur.execute("""
        INSERT INTO search.representation (source_entity_type, source_entity_id, representation_kind,
               preprocessing_profile_id, rendered_text, content_hash, status, metadata)
        SELECT entity_type, source_entity_id, kind, %s, rendered_text, content_hash, 'ACTIVE', metadata
          FROM pedagogy_vector_stage
        ON CONFLICT (source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id, content_hash)
        DO UPDATE SET status='ACTIVE', metadata=EXCLUDED.metadata
        WHERE search.representation.status IS DISTINCT FROM 'ACTIVE'
           OR search.representation.metadata IS DISTINCT FROM EXCLUDED.metadata
        RETURNING (xmax = 0)""", (profile_id,))
    rep_flags = [row[0] for row in cur.fetchall()]
    cur.execute("""
        INSERT INTO search.chunk (representation_id, chunk_ordinal, chunk_kind, chunk_text, chunk_hash,
               token_count, char_count, problem_id, solution_id, solution_step_id, learning_item_id,
               skill_node_id, subconcept_node_id, concept_node_id, metadata)
        SELECT r.representation_id, 0, 'FULL', s.rendered_text, s.content_hash, s.token_count, s.char_count,
               s.problem_id, s.solution_id, s.solution_step_id, s.learning_item_id,
               s.skill_node_id, s.subconcept_node_id, s.concept_node_id, s.metadata
          FROM pedagogy_vector_stage s
          JOIN search.representation r
            ON r.source_entity_type=s.entity_type AND r.source_entity_id=s.source_entity_id
           AND r.representation_kind=s.kind AND r.preprocessing_profile_id=%s AND r.content_hash=s.content_hash
        ON CONFLICT (representation_id, chunk_ordinal) DO UPDATE SET
               problem_id=EXCLUDED.problem_id, solution_id=EXCLUDED.solution_id,
               solution_step_id=EXCLUDED.solution_step_id, learning_item_id=EXCLUDED.learning_item_id,
               skill_node_id=EXCLUDED.skill_node_id, subconcept_node_id=EXCLUDED.subconcept_node_id,
               concept_node_id=EXCLUDED.concept_node_id, metadata=EXCLUDED.metadata
        WHERE (search.chunk.problem_id, search.chunk.solution_id, search.chunk.solution_step_id,
               search.chunk.learning_item_id, search.chunk.skill_node_id, search.chunk.subconcept_node_id,
               search.chunk.concept_node_id, search.chunk.metadata)
              IS DISTINCT FROM
              (EXCLUDED.problem_id, EXCLUDED.solution_id, EXCLUDED.solution_step_id, EXCLUDED.learning_item_id,
               EXCLUDED.skill_node_id, EXCLUDED.subconcept_node_id, EXCLUDED.concept_node_id, EXCLUDED.metadata)
        RETURNING (xmax = 0)""", (profile_id,))
    chunk_flags = [row[0] for row in cur.fetchall()]
    return {
        "staged": len(rows),
        "steps": sum(r.kind == STEP_KIND for r in rows),
        "learning_items": len({r.learning_item_id for r in rows if r.learning_item_id}),
        "taxonomy_nodes": sum(r.kind == TAXONOMY_KIND for r in rows),
        "representations_new": sum(rep_flags), "representations_updated": len(rep_flags) - sum(rep_flags),
        "chunks_new": sum(chunk_flags), "chunks_updated": len(chunk_flags) - sum(chunk_flags),
        "superseded": superseded,
    }


RECONCILE_SQL = """
WITH eligible AS (
    SELECT 'SOLUTION_STEP' AS kind, count(*) AS n FROM pedagogy.solution_step WHERE publication_status='PUBLISHED'
    UNION ALL
    SELECT k, count(*) FROM pedagogy.learning_item,
           unnest(ARRAY['LEARNING_ITEM_QUESTION','LEARNING_ITEM_SKILL_SIGNATURE']) k
     WHERE review_status='APPROVED' AND student_visible AND no_proof GROUP BY k
    UNION ALL
    SELECT 'TAXONOMY_NODE', count(*) FROM pedagogy.taxonomy_node
), active AS (
    SELECT r.representation_kind AS kind, count(DISTINCT r.representation_id) AS reps,
           count(DISTINCT e.chunk_id) FILTER (WHERE e.status='ACTIVE') AS embedded
      FROM search.representation r
      JOIN search.preprocessing_profile p USING (preprocessing_profile_id)
      LEFT JOIN search.chunk c USING (representation_id)
      LEFT JOIN search.embedding e ON e.chunk_id=c.chunk_id AND e.embedding_model_id=%s
     WHERE p.name=%s AND p.version=%s AND r.status='ACTIVE'
     GROUP BY 1
)
SELECT k.kind, coalesce(el.n, 0), coalesce(a.reps, 0), coalesce(a.embedded, 0)
  FROM unnest(%s::text[]) k(kind)
  LEFT JOIN eligible el ON el.kind=k.kind
  LEFT JOIN active a ON a.kind=k.kind
 ORDER BY 1
"""


def reconcile(cur, model_id: str) -> list[dict]:
    cur.execute(RECONCILE_SQL, (model_id, PROFILE_NAME, PROFILE_VERSION, KINDS))
    return [
        {"kind": kind, "eligible": eligible, "active_representations": reps, "embedded": embedded,
         "reconciled": eligible == reps == embedded}
        for kind, eligible, reps, embedded in cur.fetchall()
    ]


def record_report(cur, summary: dict) -> None:
    cur.execute(
        "UPDATE ingest.content_package SET report = coalesce(report, '{}'::jsonb) || %s::jsonb",
        (json.dumps({"vector_projection": summary}, default=str),),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["build", "backfill", "status", "papers"])
    args = parser.parse_args()

    with embed_corpus._connect() as conn, conn.cursor() as cur:
        if args.command == "papers":
            # Emits --paper arguments so embed_corpus.py can embed textbook problem statements/solutions.
            cur.execute("""SELECT DISTINCT pa.external_code FROM pedagogy.problem_source_ref r
                             JOIN core.problem p USING (problem_id) JOIN core.paper pa USING (paper_id)
                            ORDER BY 1""")
            print(" ".join(f"--paper {code}" for (code,) in cur.fetchall()))
            return
        model_id, _ = embed_corpus.ensure_model_and_profile(cur)
        profile_id = ensure_profile(cur)
        conn.commit()
        if args.command in ("build", "backfill"):
            built = build(cur, profile_id)
            conn.commit()
            print("build:", json.dumps(built))
        if args.command == "backfill":
            embed_corpus._ensure_openai_api_key()
            embedded, failed = embed_corpus.embed_pending_chunks(
                cur, conn, model_id, None, representation_kinds=KINDS)
            print(f"embedded: {embedded} failed: {failed}")
            if failed:
                raise SystemExit(f"{failed} step/item/taxonomy chunks failed to embed; re-run backfill")
        rows = reconcile(cur, model_id)
        for row in rows:
            print(f"  {row['kind']:<32} eligible={row['eligible']:<6} active={row['active_representations']:<6} "
                  f"embedded={row['embedded']:<6} {'OK' if row['reconciled'] else 'MISMATCH'}")
        if args.command == "backfill":
            record_report(cur, {"profile": f"{PROFILE_NAME}/v{PROFILE_VERSION}", "model": embed_corpus.MODEL_NAME,
                                "kinds": rows, "reconciled": all(r["reconciled"] for r in rows)})
            conn.commit()
        if not all(r["reconciled"] for r in rows) and args.command != "build":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
