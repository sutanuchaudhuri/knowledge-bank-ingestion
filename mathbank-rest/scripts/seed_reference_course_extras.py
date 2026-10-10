"""Extend the three reference micro-courses (seeded by seed_reference_courses.py)
with a real, curated YouTube video state and PRE/INTERMEDIATE/POST quiz states,
sourced from the human-curated reference packages under
INTERACTION_TEMPLATE_LIBRARY_COPILOT/reference_zips/*_microcourse_v1/.

Why a new release rather than editing the published one: migration 033/034
triggers make a PUBLISHED course's identity, states, and bound interactions
immutable. This creates release v2 (parent = the current published release),
carries the existing approved interaction forward onto a new EXPLORE state,
adds the new states, and publishes v2 — which supersedes v1 automatically,
exactly like any other course revision through micro_course_service.

Quiz questions are stored as activity.definition rows (source_type
INSTRUCTOR_CREATED, persistence_mode STATIC) attached via attach_activity,
*not* pedagogy.learning_item: that table is keyed to the textbook/corpus
transformation pipeline (source_problem_id/content_package_id/book_code) and
is not meant for freeform quiz authoring. The quiz/video states are left
required=False/skippable=True: there is no persisted learner-response runtime
yet (see requirements/40_MICRO_COURSE_PLATFORM.md), so these are preview-only
content blocks, and optional video states also skip migration 032's
approved-timestamped-transcript gate for REQUIRED video states (the source
packages explicitly mark every video's transcript PENDING_IMPORT, so claiming
an approved transcript here would be fabricated).

Usage:
    cd mathbank-rest && .venv/bin/python scripts/seed_reference_course_extras.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text

from mathbank_rest import micro_course_service as svc
from mathbank_rest.db.postgres import engine

SEED_AUTHOR = "reference-course-seed"


def _hash(payload) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"extra:{digest[:32]}"


def ensure_video_asset(conn, *, url: str, title: str, channel: str | None = None) -> str:
    """Insert (or reuse) an external, non-private visual.asset row pointing at a
    curated YouTube URL. No pedagogy.video_asset row is created: that table's
    APPROVED transcript gate only matters for REQUIRED video states, and these
    states are intentionally optional/preview-only (see module docstring)."""
    existing = conn.execute(
        text("SELECT asset_id FROM visual.asset WHERE source_url=:url"), {"url": url}
    ).scalar_one_or_none()
    if existing is not None:
        return str(existing)
    return str(
        conn.execute(
            text("""
            INSERT INTO visual.asset
                (uri, mime_type, content_hash, source_url, asset_kind, title,
                 rights_note, created_by_agent, persistence_mode, validation_status,
                 reviewed_by, reviewed_at)
            VALUES (:url, 'video/youtube', :hash, :url, 'VIDEO', :title,
                    :rights, :author, 'STATIC', 'VALID', :author, now())
            RETURNING asset_id
        """),
            {
                "url": url,
                "hash": _hash({"url": url, "title": title}),
                "title": title,
                "rights": f"Embedded via YouTube's standard player ({channel or 'public video'}); "
                "no local copy is stored or redistributed.",
                "author": SEED_AUTHOR,
            },
        ).scalar_one()
    )


def ensure_activity(conn, *, prompt: str, activity_type: str, options: list[str],
                     correctness_policy: dict, target_skill: str | None = None) -> str:
    content_hash = _hash({"prompt": prompt, "options": options, "policy": correctness_policy})
    existing = conn.execute(
        text("""
        SELECT activity_id FROM activity.definition
        WHERE prompt=:prompt AND source_lineage->>'content_hash'=:hash
    """),
        {"prompt": prompt, "hash": content_hash},
    ).scalar_one_or_none()
    if existing is not None:
        return str(existing)
    return str(
        conn.execute(
            text("""
            INSERT INTO activity.definition
                (activity_type, prompt, options, correctness_policy, target_skill,
                 source_type, source_lineage, persistence_mode, created_by)
            VALUES (:type, :prompt, CAST(:options AS jsonb), CAST(:policy AS jsonb), :skill,
                    'INSTRUCTOR_CREATED', CAST(:lineage AS jsonb), 'STATIC', :author)
            RETURNING activity_id
        """),
            {
                "type": activity_type,
                "prompt": prompt,
                "options": json.dumps(options),
                "policy": json.dumps(correctness_policy),
                "skill": target_skill,
                "lineage": json.dumps({
                    "content_hash": content_hash,
                    "source": "INTERACTION_TEMPLATE_LIBRARY_COPILOT/reference_zips",
                }),
                "author": SEED_AUTHOR,
            },
        ).scalar_one()
    )


def mcq(prompt: str, options: list[str], answer_index: int, explanation: str, skill: str | None = None) -> dict:
    return {
        "prompt": prompt,
        "activity_type": "MCQ",
        "options": options,
        "correctness_policy": {"correct_index": answer_index, "explanation": explanation},
        "target_skill": skill,
    }


def numeric(prompt: str, answer, explanation: str, skill: str | None = None) -> dict:
    return {
        "prompt": prompt,
        "activity_type": "NUMERIC",
        "options": [],
        "correctness_policy": {"correct_value": answer, "explanation": explanation},
        "target_skill": skill,
    }


# --- Quiz content, curated from the reference packages ---------------------------------------

MARKOV_PRE = [
    mcq(
        "Which row can be a valid probability transition row?",
        ["(0.2, 0.3, 0.5)", "(0.3, 0.3, 0.5)", "(-0.1, 0.6, 0.5)", "(2, 0, 0)"],
        0, "All entries must be nonnegative and sum to 1.", "prob-markov",
    ),
    mcq(
        "What does matrix multiplication P² represent for a transition matrix P?",
        ["Two-step transition probabilities", "Squaring each probability",
         "Two independent copies", "Only absorbing probabilities"],
        0, "The (i, j) entry of P² sums over every intermediate state.", "prob-markov",
    ),
    mcq(
        "For an event that has already occurred, the probability of eventually reaching that "
        "same target is:",
        ["1", "0", "1/2", "Undefined"],
        0, "This becomes a boundary condition h_target = 1 in a hitting-probability system.",
        "prob-markov",
    ),
]
MARKOV_INTERMEDIATE = [
    mcq(
        "What information should a Markov state contain?",
        ["Exactly enough information to determine next-step probabilities",
         "The entire history always", "Only the previous random number",
         "As little information as possible even if future probabilities change"],
        0, "A state must be sufficient: enough history for the next-step law to depend only "
        "on the state.", "prob-markov",
    ),
    mcq(
        "Every transition-matrix row must:",
        ["Sum to 1", "Sum to 0", "Have a diagonal 1", "Be identical"],
        0, "A row lists the full conditional distribution of the next state from one current "
        "state.", "prob-markov",
    ),
    mcq(
        "If μ₀ is a row distribution, the distribution after n steps is:",
        ["μ₀Pⁿ", "Pⁿμ₀", "μ₀ + nP", "P elementwise to the power n"],
        0, "Under the row-vector convention, μ_(n+1) = μ_nP.", "prob-markov",
    ),
]
MARKOV_POST = [
    mcq(
        "Target asks probability of being in state A exactly after 100 steps. Best "
        "representation if the state space is small?",
        ["Transition matrix power or an equivalent recurrence", "Absorption time equation only",
         "Bayes' theorem alone", "Geometry"],
        0, "Finite n-step distributions are naturally obtained by recurrence or Pⁿ.",
        "prob-markov",
    ),
    mcq(
        "In a finite irreducible aperiodic chain, the long-run distribution is governed by:",
        ["The unique stationary distribution", "The initial state forever",
         "Only absorbing states", "The largest matrix entry"],
        0, "Under these hypotheses, distributions converge to the unique stationary "
        "distribution.", "prob-markov",
    ),
]

VIETA_PRE = [
    mcq(
        "If Δ = b² − 4ac < 0 for real coefficients, the quadratic has:",
        ["Two nonreal conjugate roots", "Two distinct real roots", "One repeated real root",
         "No complex roots"],
        0, "A negative discriminant produces a complex-conjugate pair.", "alg-vieta",
    ),
    mcq(
        "If roots r, s satisfy r + s = 5 and rs = 6, which monic quadratic has those roots?",
        ["x² − 5x + 6", "x² + 5x + 6", "x² − 6x + 5", "x² + 6x − 5"],
        0, "(x − r)(x − s) = x² − (r + s)x + rs = x² − 5x + 6.", "alg-vieta",
    ),
]
VIETA_INTERMEDIATE = [
    mcq(
        "For 2x² − 7x + 3 = 0 with roots r, s, what is r + s?",
        ["7/2", "-7/2", "3/2", "-3/2"],
        0, "Vieta gives r + s = -b/a = -(-7)/2 = 7/2.", "alg-vieta",
    ),
    mcq(
        "For x³ + 4x² − 5x + 6 = 0 with roots a, b, c, what is abc?",
        ["-6", "6", "-4", "5"],
        0, "For a monic cubic x³ + Ax² + Bx + C, abc = -C, so abc = -6.", "alg-vieta",
    ),
    mcq(
        "Which coefficient of a monic cubic determines ab + bc + ca?",
        ["Coefficient of x", "Coefficient of x²", "Constant term with a minus sign",
         "Leading coefficient only"],
        0, "For x³ + Ax² + Bx + C, ab + bc + ca = B.", "alg-vieta",
    ),
    mcq(
        "For a nonmonic polynomial, what must be done before reading off Vieta ratios?",
        ["Divide the relevant coefficients by the leading coefficient", "Differentiate the "
         "polynomial", "Square the roots", "Assume the leading coefficient is 1"],
        0, "The general formulas use coefficient ratios a_(n-k)/a_n.", "alg-vieta",
    ),
]
VIETA_POST = [
    mcq(
        "For a monic polynomial, what is the relation between p1 = Σrᵢ and e1?",
        ["p1 = e1", "p1 = -e1", "p1 = e1²", "p1 = e2"],
        0, "The first power sum and first elementary symmetric sum are both the sum of roots.",
        "alg-vieta",
    ),
    mcq(
        "Which identity expresses p2 in terms of e1, e2 (Newton's identities)?",
        ["p2 = e1·p1 − 2e2", "p2 = e1 + 2e2", "p2 = e2·p1", "p2 = e1·p1 + 2e2"],
        0, "Newton's second identity gives p2 − e1p1 + 2e2 = 0.", "alg-vieta",
    ),
]

JENSEN_PRE = [
    mcq(
        "For x, y > 0, which is AM-GM?",
        ["(x+y)/2 ≥ √(xy)", "(x+y)/2 ≤ √(xy)", "x+y ≥ xy", "√x + √y ≥ x+y"],
        0, "The arithmetic mean is at least the geometric mean.", "ineq-jensen",
    ),
    mcq(
        "When does equality hold in AM-GM for positive x1, ..., xn?",
        ["One variable is zero", "All variables are equal", "Their product is 1",
         "n is even"],
        1, "Equality holds exactly when all compared inputs are equal.", "ineq-jensen",
    ),
    numeric(
        "If x, y > 0 and x + y = 12, what is the maximum value of xy?",
        36, "√(xy) ≤ 6, so xy ≤ 36, with equality at x = y = 6.", "ineq-jensen",
    ),
]
JENSEN_INTERMEDIATE = [
    mcq(
        "For convex f and normalized weights, Jensen's inequality gives:",
        ["f(Σλᵢxᵢ) ≤ Σλᵢf(xᵢ)", "f(Σλᵢxᵢ) ≥ Σλᵢf(xᵢ)", "f(Σxᵢ) = Σf(xᵢ)", "Σλᵢf(xᵢ) ≤ 0"],
        0, "For convex f, f at the weighted mean lies below the weighted mean of f-values.",
        "ineq-jensen",
    ),
    mcq(
        "For concave f, Jensen's inequality:",
        ["Stays exactly the same", "Reverses direction", "Forces negative weights",
         "Makes equality impossible"],
        1, "Concavity reverses Jensen's inequality.", "ineq-jensen",
    ),
    mcq(
        "Before applying Jensen's inequality, you must check:",
        ["Differentiability at one point", "Convexity/concavity on the full relevant "
         "interval and normalized weights", "All xᵢ are integers", "f is a polynomial"],
        1, "Jensen's inequality is interval- and domain-sensitive.", "ineq-jensen",
    ),
]
JENSEN_POST = [
    mcq(
        "Which function derives Weighted AM-GM from Jensen's inequality on positive inputs?",
        ["log x", "x²", "1/x", "sin x on all reals"],
        0, "log is concave on x > 0; exponentiating Jensen's inequality gives Weighted "
        "AM-GM.", "ineq-jensen",
    ),
    mcq(
        "Correct weighted AM-GM form for weights 2/3 and 1/3?",
        ["(2x+y)/3 ≥ x^(2/3)y^(1/3)", "(2x+y)/3 ≥ x^(1/3)y^(2/3)", "2x+y ≥ x²y",
         "x+y ≥ x^(2/3)y^(1/3)"],
        0, "Arithmetic coefficients and geometric exponents use the same normalized "
        "weights.", "ineq-jensen",
    ),
]

COURSE_EXTRAS = [
    {
        "canonical_code": "MC-MARKOV-STREAKS",
        "video": {
            "url": "https://www.youtube.com/watch?v=8AJPs3gvNlY",
            "title": "Lecture 31: Markov Chains | Statistics 110 (Harvard University)",
        },
        "pre": MARKOV_PRE,
        "intermediate": MARKOV_INTERMEDIATE,
        "post": MARKOV_POST,
    },
    {
        "canonical_code": "MC-VIETA-FORMULAS",
        "video": {
            "url": "https://www.youtube.com/watch?v=CCZNMGvGKQQ",
            "title": "Vieta's Formulas and the Roots of a Polynomial | Thinking Numerically",
        },
        "pre": VIETA_PRE,
        "intermediate": VIETA_INTERMEDIATE,
        "post": VIETA_POST,
    },
    {
        "canonical_code": "MC-JENSEN-INEQUALITY",
        "video": {
            "url": "https://www.youtube.com/watch?v=CPlSjinOpFo&t=7248s",
            "title": "An Inequality Solver's Heaven | 15+ Classical Inequalities "
            "(Mathsmerizing) — Jensen's inequality chapter",
        },
        "pre": JENSEN_PRE,
        "intermediate": JENSEN_INTERMEDIATE,
        "post": JENSEN_POST,
    },
]


def extend_course(conn, spec: dict) -> dict:
    code = spec["canonical_code"]
    published = conn.execute(
        text("""
        SELECT r.release_id, r.micro_course_id
        FROM pedagogy.micro_course c
        JOIN pedagogy.micro_course_release r
          ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
        WHERE c.canonical_code=:code
    """),
        {"code": code},
    ).mappings().one_or_none()
    if published is None:
        raise RuntimeError(f"{code}: no published release found; run seed_reference_courses.py first")

    already_extended = conn.execute(
        text("""
        SELECT 1 FROM pedagogy.micro_course_state
        WHERE release_id=:release_id AND state_type='VIDEO'
    """),
        {"release_id": str(published["release_id"])},
    ).scalar_one_or_none()
    if already_extended is not None:
        return {"canonical_code": code, "status": "ALREADY_EXTENDED"}

    old_release_id = str(published["release_id"])
    old_states = [
        dict(row)
        for row in conn.execute(
            text("SELECT state_id, state_key, ordinal, state_type, title, objective, "
                 "student_instruction FROM pedagogy.micro_course_state WHERE release_id=:id "
                 "ORDER BY ordinal"),
            {"id": old_release_id},
        ).mappings()
    ]
    explore_state = next(s for s in old_states if s["state_type"] == "VISUAL")
    old_interactions = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT interaction_instance_id, ordinal, required
            FROM pedagogy.micro_course_state_interaction WHERE state_id=:id ORDER BY ordinal
        """),
            {"id": str(explore_state["state_id"])},
        ).mappings()
    ]

    release_id = svc.create_release(conn, code, SEED_AUTHOR, parent_release_id=old_release_id)

    pre_id = svc.add_state(
        conn, release_id, "PRE_CHECK", 0, "DIAGNOSTIC", "Before you start",
        objective="Confirm the prerequisite ideas this lesson builds on.",
        student_instruction="A quick, ungraded check — use it to spot gaps before the lesson.",
        required=False, skippable=True,
    )
    video_id = svc.add_state(
        conn, release_id, "WATCH", 1, "VIDEO", "Watch first",
        objective="See a worked, expert explanation before exploring interactively.",
        student_instruction="This curated video is optional background; it isn't required to "
        "continue.",
        required=False, skippable=True,
    )
    asset_id = ensure_video_asset(conn, url=spec["video"]["url"], title=spec["video"]["title"])
    svc.attach_asset(conn, video_id, asset_id, 0, "PRIMARY")

    explore_id = svc.add_state(
        conn, release_id, explore_state["state_key"], 2, explore_state["state_type"],
        explore_state["title"], objective=explore_state["objective"],
        student_instruction=explore_state["student_instruction"], required=True,
    )
    for interaction in old_interactions:
        svc.attach_interaction(
            conn, explore_id, str(interaction["interaction_instance_id"]),
            interaction["ordinal"], required=interaction["required"],
        )

    intermediate_id = svc.add_state(
        conn, release_id, "CHECKPOINT", 3, "CHECKPOINT", "Checkpoint",
        objective="Confirm the core idea landed before moving on.",
        student_instruction="A short, ungraded checkpoint.",
        required=False, skippable=True,
    )
    post_id = svc.add_state(
        conn, release_id, "TRANSFER", 4, "QUIZ", "Transfer quiz",
        objective="Apply the idea in a new setting.",
        student_instruction="A short, ungraded transfer quiz.",
        required=False, skippable=True,
    )

    for state_id, purpose, questions in (
        (pre_id, "ENTRY_CHECK", spec["pre"]),
        (intermediate_id, "COMPREHENSION", spec["intermediate"]),
        (post_id, "TRANSFER", spec["post"]),
    ):
        for ordinal, question in enumerate(questions):
            activity_id = ensure_activity(
                conn,
                prompt=question["prompt"],
                activity_type=question["activity_type"],
                options=question["options"],
                correctness_policy=question["correctness_policy"],
                target_skill=question.get("target_skill"),
            )
            svc.attach_activity(conn, state_id, activity_id, ordinal, purpose, required=False)

    for from_id, to_id in (
        (pre_id, video_id), (video_id, explore_id), (explore_id, intermediate_id),
        (intermediate_id, post_id),
    ):
        svc.add_transition(conn, release_id, from_id, to_id, "NEXT")

    errors = svc.validate_release(conn, release_id)
    if errors:
        raise RuntimeError(f"{code} validate_release failed: {errors}")
    review = svc.review_release(conn, release_id, "APPROVED", SEED_AUTHOR,
                                 note="Add curated video + pre/intermediate/post quiz states.")
    if review["status"] != "APPROVED":
        raise RuntimeError(f"{code} review_release failed: {review}")
    publish = svc.publish_release(conn, release_id, SEED_AUTHOR)
    if publish["status"] != "PUBLISHED":
        raise RuntimeError(f"{code} publish_release failed: {publish}")
    return {"canonical_code": code, "status": "PUBLISHED", "release_id": release_id}


def main() -> None:
    report = []
    with engine.begin() as conn:
        for spec in COURSE_EXTRAS:
            report.append(extend_course(conn, spec))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
