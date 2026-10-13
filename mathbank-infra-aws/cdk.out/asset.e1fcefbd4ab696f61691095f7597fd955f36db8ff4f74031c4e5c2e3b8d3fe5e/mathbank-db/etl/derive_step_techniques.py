"""Derive step → technique tags for textbook solution steps (NYI-3, requirements/26 WP1).

The Prasolov pedagogy_v3 packages tag techniques per *problem* (``problem_enrichment.technique_ids``),
never per step. This ETL writes ``pedagogy.solution_step_technique`` with per-row provenance:

* ``RULE_STEP_TEXT_IN_PROBLEM`` (0.85) — the step text names one of the problem's own techniques.
* ``RULE_STEP_TEXT_NAMED``      (0.80) — the step names a specific theorem/method (Menelaus, inversion …),
  allowed even when the problem-level list omits it.
* ``RULE_STEP_FORMULA``         (0.90 / 0.70) — formula signature: ``R² − OX²`` is a point's power; an equal
  product of segments counts only when the problem already lists power of a point.
* ``LLM`` (opt-in, paid, ``--llm``) — one call per solution for steps the rules left untagged, choosing
  from a *closed* candidate list. Never run without ``--llm`` and an explicit ``--max-calls``.

Rejected design (measured 2026-05): "technique SUPPORTS the step's subconcept" (12k noisy tags) and
"problem has a single technique → every step uses it" (most steps are setup/algebra, not the technique).

Idempotent. Human rows (``source_type = 'HUMAN'``) and ``REJECTED`` rows are never overwritten or pruned;
stale RULE rows of the current scope are pruned. Only ``--book`` steps are touched (default the Prasolov
book); other corpora have no ``solution_step`` rows and stay empty by design (runtime tier, WP1.4).

Usage (from mathbank-db/etl, Neon via ``PG_ENV_FILE=../../mathbank-graph/remote.env``)::

    ../.venv/bin/python derive_step_techniques.py --dry-run
    ../.venv/bin/python derive_step_techniques.py
    ../.venv/bin/python derive_step_techniques.py --status
    ../.venv/bin/python derive_step_techniques.py --llm --max-calls 50   # paid; ask first
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

RULE_VERSION = "rules-v1"
DEFAULT_BOOK = "PRASOLOV_PGV1"
PREFIX = "TECH.GEO."
CONF_IN_PROBLEM, CONF_NAMED, CONF_FORMULA, CONF_FORMULA_WEAK = 0.85, 0.80, 0.90, 0.70
CONF_LLM_CLOSED, CONF_LLM_OPEN = 0.70, 0.60

# (pattern, named). ``named`` patterns identify a specific theorem/method and may tag a step even when the
# problem-level technique list omits it; generic patterns ("parallel", "similar") only confirm a technique
# the problem already lists. Every TECHNIQUE taxonomy node must have an entry (checked at run time).
KEYWORDS: dict[str, tuple[str, bool]] = {
    "PARALLEL_LINE_GEOMETRY": (r"parallel|∥", False),
    "PERPENDICULARITY": (r"perpendicular|⊥|right angle", False),
    "MIDPOINT_GEOMETRY": (r"midpoint|midline|middle line", False),
    "MIDLINE_MIDPOINT_GEOMETRY": (r"midline|midpoint|middle line", False),
    "GEOMETRIC_CONSTRUCTION": (r"\bconstruct|\bdraw\b|\bdrop\b|\bextend|take (a |the )?point", False),
    "CIRCLE_TANGENCY": (r"tangen", False),
    "AREA_METHOD": (r"\barea|\bS_?[A-Z]{3}", False),
    "ALTITUDES": (r"altitude|\bheight", False),
    "SYMMETRY": (r"symmetr|reflect", False),
    "ANGLE_BISECTORS": (r"bisector|bisect", False),
    "ROTATION": (r"rotat", True),
    "MEDIANS": (r"\bmedian", False),
    "INEQUALITIES": (r"inequalit|≤|≥", False),
    "VECTORS": (r"vector|−−→", False),
    "HOMOTHETY": (r"homothet", True),
    "LOCUS": (r"\blocus|\bloci\b", True),
    "CONVEXITY": (r"convex", False),
    "PROJECTIVE_TRANSFORMATIONS": (r"projective", True),
    "COORDINATE_GEOMETRY": (r"coordinate", False),
    "CENTER_OF_MASS": (r"cent(er|re) of mass|\bmasses\b", True),
    "INVERSION": (r"inversion|\binvert", True),
    "SIMILARITY": (r"similar|similitude", False),
    "SIMILAR_TRIANGLES": (r"similar|∼", False),
    "CONCYCLICITY": (r"concyclic|on (one|a|the same) circle|inscribed in a circle", False),
    "CYCLIC_QUADRILATERAL": (r"cyclic|inscribed quadrilateral", False),
    "TRIGONOMETRIC_RELATIONS": (r"\b(sin|cos|tan|cot)\b", False),
    "INDUCTION": (r"induction|inductive", True),
    "LAW_OF_SINES": (r"law of sines|sine (theorem|rule|law)", True),
    "LAW_OF_COSINES": (r"law of cosines|cosine (theorem|rule|law)", True),
    "RADICAL_AXIS": (r"radical (axis|axes|center|centre)", True),
    "ORTHOCENTER": (r"orthocent", False),
    "INSCRIBED_GEOMETRY": (r"inscribed|incircle|incent", False),
    "EXTREMAL_OPTIMIZATION": (r"maxim|minim|greatest|smallest|largest", False),
    "EXTREMAL_PRINCIPLE": (r"extremal|greatest|largest|smallest", False),
    "CONVEX_HULL": (r"convex hull", True),
    "COLORINGS": (r"colou?r", False),
    "INTEGER_LATTICE": (r"lattice|integer (point|coordinate)", True),
    "SIMSON_LINE": (r"simson", True),
    "MENELAUS_THEOREM": (r"menelaus", True),
    "CEVA_THEOREM": (r"\bceva", True),
    "PTOLEMY_THEOREM": (r"ptolemy", True),
    "BARYCENTRIC_COORDINATES": (r"barycentric", True),
    "INVARIANTS": (r"invariant", True),
    "TRIANGLE_INEQUALITY": (r"triangle inequality", True),
    "PIGEONHOLE_PRINCIPLE": (r"pigeonhole|dirichlet", True),
    "NINE_POINT_CIRCLE": (r"nine-?point", True),
    "CROSS_RATIO": (r"cross[- ]ratio", True),
    "LEMOINE_POINT": (r"lemoine|symmedian", True),
    "DISSECTIONS_CUTTINGS": (r"\bcut|dissect", False),
    "DOT_PRODUCT": (r"dot product|scalar product|inner product", True),
    "AFFINE_TRANSFORMATIONS": (r"affine", True),
    "HELLY_THEOREM": (r"helly", True),
    # Not "powers? of" alone: it matches "power of a prime".
    "POWER_OF_A_POINT": (r"power of (the |a )?point|(?-i:[Pp]ower of [A-Z]\b)|powers? with respect to", True),
    "COMBINATORICS": (r"combinator|number of ways", False),
}
_PATTERNS = {PREFIX + k: (re.compile(p, re.I), named) for k, (p, named) in KEYWORDS.items()}

POWER = PREFIX + "POWER_OF_A_POINT"
# Prasolov's PDF text loses superscripts: "R² − OX²" arrives as "R2 −OX2".
_FORMULA_POWER = re.compile(r"R\s?[2²]\s?[−-]\s?[A-Z]{2}\s?[2²]|[A-Z]{2}\s?[2²]\s?[−-]\s?R\s?[2²]")
_FORMULA_PRODUCT = re.compile(
    r"\b[A-Z]{2}\d?\s?·\s?[A-Z]{2}\d?\s?=\s?[A-Z]{2}\d?\s?·\s?[A-Z]{2}\d?\b"
    r"|\b[A-Z]{2}\d?\s?[2²]\s?=\s?[A-Z]{2}\d?\s?·\s?[A-Z]{2}\d?")


def derive(step_text: str | None, problem_techniques: list[str] | None) -> dict[str, tuple[str, float, str]]:
    """Pure rule tier: ``{technique_id: (source_type, confidence, evidence)}`` for one step."""
    text_ = step_text or ""
    allowed = [t for t in (problem_techniques or []) if t in _PATTERNS]
    out: dict[str, tuple[str, float, str]] = {}
    m = _FORMULA_POWER.search(text_)
    if m:
        out[POWER] = ("RULE_STEP_FORMULA", CONF_FORMULA, m.group(0))
    for tech in allowed:
        if tech in out:
            continue
        m = _PATTERNS[tech][0].search(text_)
        if m:
            out[tech] = ("RULE_STEP_TEXT_IN_PROBLEM", CONF_IN_PROBLEM, m.group(0))
    for tech, (pattern, named) in _PATTERNS.items():
        if named and tech not in out:
            m = pattern.search(text_)
            if m:
                out[tech] = ("RULE_STEP_TEXT_NAMED", CONF_NAMED, m.group(0))
    if POWER in allowed and POWER not in out:
        m = _FORMULA_PRODUCT.search(text_)
        if m:
            out[POWER] = ("RULE_STEP_FORMULA", CONF_FORMULA_WEAK, m.group(0))
    return out


STEP_SQL = """
SELECT st.solution_step_id, st.solution_id, st.global_step_index, st.step_text,
       coalesce(pe.technique_ids, '{}') AS technique_ids
FROM pedagogy.solution_step st
LEFT JOIN pedagogy.problem_enrichment pe ON pe.problem_id = st.problem_id
WHERE st.book_code = %s
ORDER BY st.solution_id, st.global_step_index
"""

UPSERT_SQL = """
INSERT INTO pedagogy.solution_step_technique
  (solution_step_id, technique_node_id, confidence, source_type, evidence, derivation_version,
   review_status, approval_method, approved_at)
VALUES (%s, %s, %s, %s, %s, %s, 'APPROVED', 'automatic', now())
ON CONFLICT (solution_step_id, technique_node_id) DO UPDATE SET
  confidence = EXCLUDED.confidence, source_type = EXCLUDED.source_type, evidence = EXCLUDED.evidence,
  derivation_version = EXCLUDED.derivation_version, updated_at = now()
WHERE solution_step_technique.source_type <> 'HUMAN'
  AND solution_step_technique.review_status <> 'REJECTED'
  AND (solution_step_technique.source_type <> 'LLM' OR EXCLUDED.source_type LIKE 'RULE_%%')
  AND (solution_step_technique.confidence, solution_step_technique.source_type,
       solution_step_technique.evidence, solution_step_technique.derivation_version)
      IS DISTINCT FROM (EXCLUDED.confidence, EXCLUDED.source_type, EXCLUDED.evidence, EXCLUDED.derivation_version)
"""

RUN_SQL = """
INSERT INTO pedagogy.solution_step_technique_run (solution_step_id, derivation_version, outcome, candidate_ids)
VALUES (%s, %s, %s, %s)
ON CONFLICT (solution_step_id, derivation_version) DO UPDATE SET
  outcome = EXCLUDED.outcome, candidate_ids = EXCLUDED.candidate_ids, created_at = now()
WHERE (solution_step_technique_run.outcome, solution_step_technique_run.candidate_ids)
      IS DISTINCT FROM (EXCLUDED.outcome, EXCLUDED.candidate_ids)
"""


def _techniques(cur) -> set[str]:
    cur.execute("SELECT taxonomy_node_id FROM pedagogy.taxonomy_node WHERE node_type = 'TECHNIQUE'")
    return {r[0] for r in cur.fetchall()}


def plan(steps: list[tuple]) -> tuple[list[tuple], list[tuple], collections.Counter]:
    rows, runs, stats = [], [], collections.Counter()
    for sid, _sol, _idx, text_, techs in steps:
        tags = derive(text_, techs)
        for tech, (source, conf, ev) in sorted(tags.items()):
            rows.append((sid, tech, conf, source, ev[:200], RULE_VERSION))
            stats[source] += 1
        outcome = "TAGGED" if tags else ("NO_MATCH" if techs else "NO_PROBLEM_TECHNIQUE")
        runs.append((sid, RULE_VERSION, outcome, list(techs)))
        stats[outcome] += 1
    return rows, runs, stats


def run_rules(conn, book: str, dry_run: bool) -> dict:
    with conn.cursor() as cur:
        known = _techniques(cur)
        missing = known ^ set(_PATTERNS)
        if missing:
            raise SystemExit(f"KEYWORDS out of sync with TECHNIQUE taxonomy: {sorted(missing)}")
        cur.execute(STEP_SQL, (book,))
        steps = cur.fetchall()
        rows, runs, stats = plan(steps)
        report = {"book": book, "steps": len(steps), "tags": len(rows), **stats}
        if dry_run:
            return report
        cur.executemany(UPSERT_SQL, rows)
        cur.executemany(RUN_SQL, runs)
        cur.execute("CREATE TEMP TABLE _keep (sid text, tid text) ON COMMIT DROP")
        with cur.copy("COPY _keep (sid, tid) FROM STDIN") as cp:
            for r in rows:
                cp.write_row((r[0], r[1]))
        cur.execute(
            """DELETE FROM pedagogy.solution_step_technique t
               USING pedagogy.solution_step s
               WHERE s.solution_step_id = t.solution_step_id AND s.book_code = %s
                 AND t.source_type LIKE 'RULE_%%' AND t.review_status <> 'REJECTED'
                 AND NOT EXISTS (SELECT 1 FROM _keep k WHERE k.sid = t.solution_step_id
                                 AND k.tid = t.technique_node_id)""", (book,))
        report["pruned"] = cur.rowcount
    conn.commit()
    return report


def status(conn, book: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(DISTINCT t.solution_step_id), count(DISTINCT t.technique_node_id)
               FROM pedagogy.solution_step_technique t JOIN pedagogy.solution_step s USING (solution_step_id)
               WHERE s.book_code = %s AND t.review_status = 'APPROVED'""", (book,))
        tags, steps_tagged, techniques = cur.fetchone()
        cur.execute("SELECT count(*) FROM pedagogy.solution_step WHERE book_code = %s", (book,))
        total = cur.fetchone()[0]
        cur.execute(
            """SELECT t.source_type, count(*) FROM pedagogy.solution_step_technique t
               JOIN pedagogy.solution_step s USING (solution_step_id) WHERE s.book_code = %s
               GROUP BY 1 ORDER BY 1""", (book,))
        by_source = dict(cur.fetchall())
        cur.execute(
            """SELECT r.outcome, count(*) FROM pedagogy.solution_step_technique_run r
               JOIN pedagogy.solution_step s USING (solution_step_id)
               WHERE s.book_code = %s AND r.derivation_version = %s GROUP BY 1 ORDER BY 1""",
            (book, RULE_VERSION))
        outcomes = dict(cur.fetchall())
    return {"book": book, "steps": total, "steps_tagged": steps_tagged, "tags": tags,
            "techniques_used": techniques, "by_source": by_source, "rule_outcomes": outcomes}


# ------------------------------------------------------------------ optional paid LLM tier
LLM_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["steps"],
    "properties": {"steps": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["step_id", "technique_ids", "reason"],
        "properties": {"step_id": {"type": "string"},
                       "technique_ids": {"type": "array", "items": {"type": "string"}},
                       "reason": {"type": "string"}}}}},
}


def validate_llm(answer: dict, step_ids: set[str], candidates: set[str]) -> list[tuple[str, str, str]]:
    """Keep only (step, technique, reason) triples for asked-about steps and closed-list techniques."""
    out = []
    for item in (answer or {}).get("steps") or []:
        sid = str(item.get("step_id"))
        if sid not in step_ids:
            continue
        for tech in item.get("technique_ids") or []:
            if tech in candidates:
                out.append((sid, tech, str(item.get("reason") or "")[:200]))
    return out


def run_llm(conn, book: str, max_calls: int, model: str) -> dict:
    from openai import OpenAI

    from embed_corpus import _ensure_openai_api_key

    _ensure_openai_api_key()  # project .env key only, never the shell profile
    client = OpenAI()
    version = f"llm-v1:{model}"
    with conn.cursor() as cur:
        cur.execute(
            """SELECT tn.taxonomy_node_id, tn.name FROM pedagogy.taxonomy_node tn
               WHERE tn.node_type = 'TECHNIQUE'""")
        names = dict(cur.fetchall())
        cur.execute(
            """SELECT st.solution_id, st.solution_step_id, st.step_text, coalesce(pe.technique_ids, '{}')
               FROM pedagogy.solution_step st
               LEFT JOIN pedagogy.problem_enrichment pe ON pe.problem_id = st.problem_id
               WHERE st.book_code = %s
                 AND NOT EXISTS (SELECT 1 FROM pedagogy.solution_step_technique t
                                 WHERE t.solution_step_id = st.solution_step_id)
                 AND NOT EXISTS (SELECT 1 FROM pedagogy.solution_step_technique_run r
                                 WHERE r.solution_step_id = st.solution_step_id AND r.derivation_version = %s)
               ORDER BY st.solution_id, st.global_step_index""", (book, version))
        by_solution: dict[str, list] = collections.defaultdict(list)
        for sol, sid, text_, techs in cur.fetchall():
            by_solution[sol].append((sid, text_, list(techs)))
    calls = tagged = 0
    for sol, steps in by_solution.items():
        if calls >= max_calls:
            break
        problem_techs = steps[0][2]
        candidates = set(problem_techs) or set(names)
        conf = CONF_LLM_CLOSED if problem_techs else CONF_LLM_OPEN
        prompt = {"techniques": {t: names[t] for t in sorted(candidates) if t in names},
                  "steps": [{"step_id": sid, "text": (t or "")[:600]} for sid, t, _ in steps]}
        response = client.chat.completions.create(
            model=model, temperature=0,
            response_format={"type": "json_schema", "json_schema": {
                "name": "step_techniques", "strict": True, "schema": LLM_SCHEMA}},
            messages=[{"role": "system", "content": (
                "For each step of a geometry solution, list the techniques (ids from the given list only) "
                "that the step itself applies. Most steps apply none; return an empty list then. Do not "
                "tag a technique merely because the problem uses it elsewhere.")},
                {"role": "user", "content": json.dumps(prompt)}])
        calls += 1
        answer = json.loads(response.choices[0].message.content or "{}")
        triples = validate_llm(answer, {s[0] for s in steps}, candidates)
        hit = {sid for sid, _, _ in triples}
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, [(sid, tech, conf, "LLM", reason, version) for sid, tech, reason in triples])
            cur.executemany(RUN_SQL, [(sid, version, "TAGGED" if sid in hit else "NO_MATCH", sorted(candidates))
                                      for sid, _, _ in steps])
        conn.commit()
        tagged += len(triples)
    return {"book": book, "model": model, "calls": calls, "llm_tags": tagged,
            "solutions_pending": max(len(by_solution) - calls, 0)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--llm", action="store_true", help="paid: tag rule-untagged steps with a model")
    ap.add_argument("--max-calls", type=int, default=0, help="required with --llm (one call per solution)")
    ap.add_argument("--model", default="gpt-4.1-mini")
    args = ap.parse_args(argv)

    from embed_corpus import _connect

    with _connect() as conn:
        if args.status:
            print(json.dumps(status(conn, args.book), indent=2, default=str))
        elif args.llm:
            if args.max_calls <= 0:
                raise SystemExit("--llm is paid: pass an explicit --max-calls N")
            print(json.dumps(run_llm(conn, args.book, args.max_calls, args.model), indent=2))
        else:
            print(json.dumps(run_rules(conn, args.book, args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
