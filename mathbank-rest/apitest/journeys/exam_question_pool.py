"""The question pool (migration 052 cache of critic-approved questions): match before and after a finalize that writes entries back,
exact-duplicate linking (content-hash sentinel), near-duplicate linking inside one finalize (prompt vectors), serving an entry to
another learner, and the per-learner 'never one this learner was already served' rule.

S3 Vectors is read from `dev` (empty QUIZ_QUESTION index) and its writes are guarded off, so the entries stay vector_state=PENDING and
the vector branch of the match never returns rows: only the concept index branch can answer. Observations are recorded as checks."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import check, finalize, good, js, mcq, onboard, scan, start_paper, svc

ENTRY_KEYS = {"pool_question_id", "question_type", "question", "topic_similarity"}
HIDDEN_IN_ENTRY = {"revision_log", "pool_question_id", "add_to_pool"}      # POOL_QUESTION_EXCLUDED_FIELDS


@journey("exam_question_pool")
def exam_question_pool(ctx: Ctx) -> None:
    a, b, c = onboard(ctx, "poola"), onboard(ctx, "poolb"), onboard(ctx, "poolc")
    if not (a and b and c):
        return
    run = ctx.run_id
    slug = f"apitest-{run}"
    topic = f"apitest {run} residues modulo seven and drawing marbles without replacement"

    def match(who, case: str, status=200, **over):
        body = {"student_id": who.sid, "style": "AIME", "question_types": ["MCQ"], "difficulty_band": "hard", "topic": topic,
                "concept_slugs": [slug], "limit": 20, **over}
        return svc(ctx, case, "POST", "/question-pool/match", status, json=body)

    def ids_of(r) -> list[str]:
        return sorted(e["pool_question_id"] for e in js(r)) if good(r) else []

    # ---- request validation (concept-only bodies: no embedding call)
    match(b, "match: limit 0", 422, limit=0, topic=None)
    match(b, "match: limit 51", 422, limit=51, topic=None)
    match(b, "match: four question types", 422, question_types=["MCQ", "FREE_TEXT", "PROOF", "MCQ"], topic=None)
    match(b, "match: unknown field", 422, topic=None, bogus=1)
    nothing = match(b, "match: no topic and no concepts", topic=None, concept_slugs=[])
    check(ctx, "match without topic and concepts is empty", good(nothing) and js(nothing) == [], str(js(nothing)))
    odd = match(b, "match: unknown style", topic=None, style="NOPE")
    check(ctx, "an unknown style matches nothing", good(odd) and js(odd) == [], str(js(odd)))
    band = match(b, "match: a difficulty band outside the vocabulary", {200, 422}, topic=None, difficulty_band="impossible")
    check(ctx, "an invalid band is a 4xx or an empty match, never a 500", band is not None and band.status_code < 500, str(band and band.status_code))
    ghost = svc(ctx, "match: unknown student", "POST", "/question-pool/match", 200,
                json={"student_id": "00000000-0000-4000-8000-0000000000a1", "style": "AIME", "concept_slugs": [slug], "difficulty_band": "hard"})
    check(ctx, "an unknown student simply has nothing served", good(ghost) and js(ghost) == [], str(js(ghost)))

    # ---- before: an unused concept slug and topic match nothing (one embedding call for the topic)
    before = match(b, "match before any write-back (topic + concept)")
    check(ctx, "pool is empty for this run's concept", good(before) and js(before) == [], str(js(before)))

    # ---- A finalizes three questions: p1, a near-identical p2 and a different p3, all written back to the pool
    p1 = f"[{run}] How many residues r modulo 7 satisfy r^2 = 2 (mod 7)?"
    p2 = f"[{run}] How many residues r modulo 7 satisfy r^2 = 2 (mod 7)"
    p3 = f"[{run}] A bag holds 5 red and 3 blue marbles; two are drawn without replacement. What is the chance both are red?"
    qid = start_paper(ctx, a.sid, count=3, style="AIME", case="A: start", title="pool write-back")
    if qid is None:
        return
    qs = [mcq(ctx, 1, prompt_text=p, add_to_pool=True, concept_slugs=[]) for p in (p1, p2, p3)]
    fin = finalize(ctx, a.sid, qid, qs, case="A: finalize with add_to_pool", pool_topic=topic, pool_concept_slugs=[slug])
    if not good(fin):
        return
    scan(ctx, "A: finalize response", fin)
    check(ctx, "A: paper READY with 3 questions", js(fin)["status"] == "READY" and len(js(fin)["questions"]) == 3, str(js(fin)["status"]))

    # ---- after: another learner now gets the cached entries; A, who was served them, gets none
    own = match(a, "A: match after own write-back")
    check(ctx, "the writer is never served its own write-back", good(own) and js(own) == [], f"{len(js(own) or [])} entries")
    seen = match(b, "B: match after A's write-back")
    entries = js(seen) if good(seen) else []
    if good(seen):
        check(ctx, "B receives the written-back questions", len(entries) >= 1, "no entry written back (or not found by concept)")
        check(ctx, "near-duplicate prompt of one finalize is linked to the earlier entry (2 entries, not 3)", len(entries) == 2,
              f"{len(entries)} distinct pool entries for 3 questions (p1 and p2 differ only by a final '.')")
        check(ctx, "entry shape", all(ENTRY_KEYS == set(e) for e in entries), str([sorted(e) for e in entries][:1]))
        check(ctx, "entry carries the full question with its answer key, minus the excluded fields",
              all({"prompt_text", "correct_answer", "solution_text"} <= set(e["question"]) and not (HIDDEN_IN_ENTRY & set(e["question"])) for e in entries),
              str([sorted(e["question"]) for e in entries][:1]))
        check(ctx, "no row came from S3 Vectors (dev QUIZ_QUESTION index is empty; entries are PENDING)",
              all(e["topic_similarity"] == 0.0 for e in entries), str([e["topic_similarity"] for e in entries]))
        check(ctx, "entries are the questions A wrote", {e["question"]["prompt_text"] for e in entries} <= {p1, p2, p3}, str({e["question"]["prompt_text"] for e in entries}))

    # ---- exact duplicate by another learner: linked through the content-hash sentinel, no new entry
    qc = start_paper(ctx, c.sid, count=1, style="AIME", case="C: start", title="pool exact duplicate")
    if qc is not None:
        finalize(ctx, c.sid, qc, [mcq(ctx, 1, prompt_text=p3, add_to_pool=True)], case="C: finalize an exact duplicate of p3",
                 pool_topic=topic, pool_concept_slugs=[slug])
        again = match(b, "B: match after C's exact duplicate")
        check(ctx, "an exact duplicate creates no new pool entry", good(again) and ids_of(again) == ids_of(seen), f"{ids_of(again)} vs {ids_of(seen)}")
        c_view = match(c, "C: match after being served p3's entry")
        if good(c_view) and good(seen):
            check(ctx, "C is not served again what its own paper linked to", len(js(c_view)) == len(entries) - 1, f"{len(js(c_view))} vs {len(entries)}")

    # ---- B finalizes a paper that serves an entry from the pool: that entry is excluded for B from then on
    if entries:
        target = entries[0]["pool_question_id"]
        qb = start_paper(ctx, b.sid, count=2, style="AIME", case="B: start", title="pool serve")
        if qb is not None:
            qs_b = [mcq(ctx, 5, pool_question_id=target), mcq(ctx, 6, pool_question_id="00000000-0000-4000-8000-0000000000a2")]
            fb = finalize(ctx, b.sid, qb, qs_b, case="B: finalize serving one pool entry and one unknown id")
            check(ctx, "B: paper READY", good(fb) and js(fb)["status"] == "READY", str(js(fb) and js(fb)["status"]))
            left = match(b, "B: match after being served an entry")
            check(ctx, "a served entry is no longer offered to the learner it was served to",
                  good(left) and target not in ids_of(left) and len(js(left)) == len(entries) - 1, f"{ids_of(left)} still has {target}")
