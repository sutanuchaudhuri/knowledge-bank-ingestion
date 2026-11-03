"""Content reads of the diagnosis and recovery areas (requirement 71 WP5; requirement 70 C6 access patterns A14, A15, A16, A24, A25).

What the diagnoser and the recovery planner need from the published content that the content store does not expose as a method yet:

* the taxonomy nodes of a step (labels, the knowledge-skill / concept uuids of the target hypothesis),
* candidate learning items for a skill (recovery practice) and short probes (diagnosis), read from the ``FACET#LI#TARGET_SUBCONCEPT#<node>``
  partitions and filtered by the same rules as the SQL (approved + visible are what ``eligible`` means in mb-content; no cross-reference stubs;
  a minimum answer length; never from the problem being solved; never a question that leaks its own solution),
* a worked example (a same-skill step of a problem the learner has not attempted) and same-skill practice steps, from ``FACET#STEP#SKILL#<skill>``.

Everything is a Query / BatchGet on ``mb-content`` through ``stores.typed`` (no scans). Server-only attributes (the answer key, solution seeds)
are used here only to filter and are never returned to the learner. The key lookups for grading go through the content store
(``get_learning_item_key``). Divergences from the SQL (listed in the WP5 report): topic closeness of a candidate uses the learning item's own target
concept / subconcept (the source problem's enrichment would need one query per problem); concept prerequisites are not available in mb-content
(``list_taxonomy_prerequisite_ids`` returns ``[]``), so a diagnosis has no CONCEPT-level hypotheses.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Any

from mathbank_rest import step_recovery_logic as logic
from mathbank_rest.models.ddb.content import (
    ContentFacet,
    ContentLi,
    ContentLiKey,
    ContentStep,
    ContentTaxnode,
)
from mathbank_rest.step_runtime import CROSS_REFERENCE_STUB_RE
from mathbank_rest.stores import typed

# the SQL stub pattern is a PostgreSQL ARE (\m, \M word anchors)
STUB = re.compile(CROSS_REFERENCE_STUB_RE.replace(r"\M", r"\b").replace(r"\m", r"\b"), re.IGNORECASE)
MIN_ANSWER_CHARS = 25
MAX_VALIDATED = 40
KEY_CHUNK = 30


def content():
    from mathbank_rest import stores

    return stores.get_store("content")


def _pages(model, pk: str, **kw) -> Iterator[Any]:
    token = None
    while True:
        page = typed.query(model, pk, limit=200, next_token=token, consistent=False, **kw)
        yield from page.items
        token = page.next_token
        if not token:
            return


# ---------------------------------------------------------------------------------------------- taxonomy

def taxonomy(node_ids: Iterable[str | None]) -> dict[str, ContentTaxnode]:
    ids = [i for i in dict.fromkeys(node_ids) if i]
    return {n.taxonomy_node_id: n for n in typed.batch_get(ContentTaxnode, [(f"TAXNODE#{i}", "META") for i in ids], consistent=False)}


# ---------------------------------------------------------------------------------------------- learning items

def _hash(student_id: str, item_id: str) -> str:
    return logic.variety(student_id, item_id)


def _lis(ids: list[str]) -> dict[str, ContentLi]:
    return {li.learning_item_id: li for li in typed.batch_get(ContentLi, [(f"LI#{i}", "META") for i in ids], consistent=False)}


def _keys(ids: list[str]) -> dict[str, ContentLiKey]:
    out: dict[str, ContentLiKey] = {}
    for i in range(0, len(ids), KEY_CHUNK):
        out |= {k.learning_item_id: k for k in typed.batch_get(ContentLiKey, [(f"LI#{x}", "KEY") for x in ids[i:i + KEY_CHUNK]], consistent=False)}
    return out


def subconcept_of_skill(skill_id: str) -> str | None:
    for facet in _pages(ContentFacet, f"FACET#STEP#SKILL#{skill_id}"):
        if facet.subconcept_node_id:
            return facet.subconcept_node_id
    return None


def learning_item_candidates(student_id: str, origin_problem_id: str, skill_id: str | None, subconcept_id: str | None, *,
                             exclude_ids: set[str], origin_subconcept: str | None = None, origin_concept: str | None = None,
                             limit: int = logic.CANDIDATE_LIMIT) -> list[dict]:
    """Safe, ordered recovery candidates for a skill (or its subconcept): ``learning_item_id, transformation_type, transformed_form,
    source_problem_id, skill_match, question_text, answer_or_solution_seed, correct_answer, statement_text, topic_closeness``."""
    if not skill_id and not subconcept_id:
        return []
    subconcept_id = subconcept_id or (subconcept_of_skill(skill_id) if skill_id else None)
    if not subconcept_id:
        return []
    rows = []
    for f in _pages(ContentFacet, f"FACET#LI#TARGET_SUBCONCEPT#{subconcept_id}"):
        li_id = f.entity_id
        if li_id in exclude_ids or (f.source_problem_id is not None and str(f.source_problem_id) == str(origin_problem_id)):
            continue
        if not (f.target_skill_node_id == skill_id and skill_id is not None or f.target_skill_node_id is None):
            continue
        rows.append({"learning_item_id": li_id, "transformation_type": f.transformation_type, "transformed_form": f.transformed_form,
                     "source_problem_id": str(f.source_problem_id) if f.source_problem_id else None,
                     "skill_match": skill_id is not None and f.target_skill_node_id == skill_id})
    if not rows:
        return []
    metas = _lis([r["learning_item_id"] for r in rows])
    rows = [r for r in rows if r["learning_item_id"] in metas and metas[r["learning_item_id"]].eligible]
    for r in rows:
        m = metas[r["learning_item_id"]]
        r["topic_closeness"] = (2 if origin_subconcept and m.target_subconcept_node_id == origin_subconcept else
                                1 if origin_concept and m.target_concept_node_id == origin_concept else 0)
    rows.sort(key=lambda r: (not r["skill_match"], -r["topic_closeness"], _hash(student_id, r["learning_item_id"])))
    rows = rows[:MAX_VALIDATED]
    keys = _keys([r["learning_item_id"] for r in rows])
    codes = list(dict.fromkeys(metas[r["learning_item_id"]].source_problem_code for r in rows))
    statements = {p["canonical_code"]: p.get("statement_text") for p in content().get_problems_by_codes(codes)}
    out = []
    for r in rows:
        m, k = metas[r["learning_item_id"]], keys.get(r["learning_item_id"])
        seed, correct = (k.resolve("answer_or_solution_seed"), k.resolve("correct_answer")) if k else (None, None)
        if len(seed or correct or "") < MIN_ANSWER_CHARS or STUB.search(seed or "") or STUB.search(correct or ""):
            continue
        row = {**r, "question_text": m.resolve("question_text"), "answer_or_solution_seed": seed, "correct_answer": correct,
               "statement_text": statements.get(m.source_problem_code)}
        if logic.safe_recovery_question(row):
            out.append(row)
    return out[:limit]


def learning_item_probes(student_id: str, problem_id: str, skill_id: str, seen_step_ids: set[str], limit: int = 3) -> list[dict]:
    """Short checks for a skill: approved learning items first (codes and metadata only, never step text), then same-skill steps from other
    problems the learner has not seen."""
    subconcept = subconcept_of_skill(skill_id)
    probes: list[dict] = []
    if subconcept:
        order = ("MCQ_METHOD_RECOGNITION", "MCQ_FIRST_MOVE", "MCQ_INTERMEDIATE_SKILL", "SUBPROBLEM_FIRST_MOVE")
        facets = [f for f in _pages(ContentFacet, f"FACET#LI#TARGET_SUBCONCEPT#{subconcept}")
                  if (f.target_skill_node_id == skill_id or f.target_skill_node_id is None)
                  and not (f.source_problem_id is not None and str(f.source_problem_id) == str(problem_id))]
        facets.sort(key=lambda f: (f.target_skill_node_id is None,
                                   order.index(f.transformation_type) if f.transformation_type in order else len(order),
                                   _hash(student_id, f.entity_id)))
        metas = _lis([f.entity_id for f in facets[:MAX_VALIDATED]])
        keys = _keys([f.entity_id for f in facets[:MAX_VALIDATED] if f.entity_id in metas and metas[f.entity_id].eligible])
        for f in facets[:MAX_VALIDATED]:
            m, k = metas.get(f.entity_id), keys.get(f.entity_id)
            if m is None or not m.eligible or k is None:
                continue
            seed, correct = k.resolve("answer_or_solution_seed"), k.resolve("correct_answer")
            if len(seed or correct or "") < MIN_ANSWER_CHARS or STUB.search(seed or "") or STUB.search(correct or ""):
                continue
            probes.append({"kind": "LEARNING_ITEM", "learning_item_id": f.entity_id, "transformation_type": m.transformation_type,
                           "transformed_form": m.transformed_form, "problem_code": m.source_problem_code})
            if len(probes) == limit:
                return probes
    steps = _skill_steps(skill_id)
    steps = [s for s in steps if str(s.problem_id) != str(problem_id) and s.solution_step_id not in seen_step_ids]
    steps.sort(key=lambda s: (not s.is_checkpoint, s.global_step_index, s.solution_step_id))
    for s in steps[:limit - len(probes)]:
        probes.append({"kind": "PRACTICE_STEP", "solution_step_id": s.solution_step_id, "problem_code": s.problem_code,
                       "global_step_index": s.global_step_index, "step_type": s.step_type, "skill_name": s.skill_name,
                       "is_checkpoint": bool(s.is_checkpoint)})
    return probes


def _skill_steps(skill_id: str) -> list[ContentStep]:
    ids = [f.entity_id for f in _pages(ContentFacet, f"FACET#STEP#SKILL#{skill_id}")]
    return [s for s in typed.batch_get(ContentStep, [(f"STEP#{i}", "META") for i in ids[:200]], consistent=False) if s.eligible]


def worked_example_step(student_id: str, origin_problem_id: str, skill_id: str | None, attempted_problem_ids: set[str], *,
                        origin_subconcept: str | None, origin_concept: str | None) -> str | None:
    """A same-skill step from a problem the learner has not attempted, short enough to show, topically close first."""
    if not skill_id:
        return None
    best: tuple | None = None
    for s in _skill_steps(skill_id):
        if str(s.problem_id) == str(origin_problem_id) or str(s.problem_id) in attempted_problem_ids:
            continue
        text = s.resolve("step_text") or ""
        if not 30 <= len(text) <= 600 or STUB.search(text):
            continue
        key = (s.subconcept_node_id != origin_subconcept or origin_subconcept is None,
               s.concept_node_id != origin_concept or origin_concept is None, not s.is_checkpoint,
               _hash(student_id, s.solution_step_id))
        if best is None or key < best[0]:
            best = (key, s.solution_step_id)
    return best[1] if best else None


def learning_item_meta(ids: Iterable[str]) -> dict[str, dict]:
    """``transformation_type``, ``transformed_form`` and ``source_problem_id`` of learning items (plan items copy them when built)."""
    return {i: {"transformation_type": m.transformation_type, "transformed_form": m.transformed_form,
                "source_problem_id": str(m.source_problem_id)} for i, m in _lis(list(dict.fromkeys(ids))).items()}


def learning_item_row(learning_item_id: str, *, with_key: bool) -> dict | None:
    """Presentation / grading row of one learning item: the item, its source problem's code and statement and, only when asked, the key."""
    li = typed.get(ContentLi, f"LI#{learning_item_id}", "META", consistent=False)
    if li is None:
        return None
    problems = content().get_problems_by_codes([li.source_problem_code])
    row = {"question_text": li.resolve("question_text"), "choices": li.resolve("choices"), "transformed_form": li.transformed_form,
           "transformation_type": li.transformation_type, "requires_source_problem": li.requires_source_problem,
           "solution_part_label": li.solution_part_label, "canonical_code": li.source_problem_code,
           "statement_text": problems[0].get("statement_text") if problems else None, "source_problem_id": str(li.source_problem_id),
           "correct_answer": None, "answer_or_solution_seed": None}
    if with_key:
        key = content().get_learning_item_key(None, learning_item_id)
        if key is not None:
            row["correct_answer"], row["answer_or_solution_seed"] = key["correct_answer"], key["answer_or_solution_seed"]
    return row
