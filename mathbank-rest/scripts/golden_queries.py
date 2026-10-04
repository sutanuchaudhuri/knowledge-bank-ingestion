"""Golden query set for retrieval evaluation (Precision@K / Recall@K / MRR / nDCG@K).

Ground truth here is *derived*, not hand-labeled: for each case, "relevant"
means "any problem tagged with this concept/technique slug" per
knowledge.problem_concept / problem_technique (i.e. whatever the
classification pipeline in mathbank_data_ingestion produced). This makes the
set cheap to keep in sync as the corpus grows (no manual relevance judgments
to maintain) at the cost of ground truth being only as good as the LLM
classification step — see scripts/evaluate_retrieval.py's docstring and
mathematics_tutor_db_plan/agent/16_observability_and_evaluation.md section 4
for the tradeoff and the path to hand-curated cases later.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenCase:
    name: str
    query: str
    # Ground truth source: exactly one of concept_slug / technique_slug.
    concept_slug: str | None = None
    technique_slug: str | None = None
    competition: str | None = None  # applied both to ground truth lookup and to the search filter
    k: int = 10


GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        name="combinatorics-general",
        query="combinatorics counting problems",
        concept_slug="count",
    ),
    GoldenCase(
        name="logarithms-and-exponentials",
        query="logarithms and exponential equations",
        concept_slug="alg-logexp",
    ),
    GoldenCase(
        name="number-theory-divisibility",
        query="number theory divisibility problems",
        concept_slug="nt-div",
    ),
    GoldenCase(
        name="geometry-circles",
        query="geometry problems about circles",
        concept_slug="geo-circle",
    ),
    GoldenCase(
        name="invariant-technique",
        query="problems solved using an invariant argument",
        technique_slug="tech-inv",
    ),
    GoldenCase(
        name="pigeonhole-principle",
        query="pigeonhole principle problems",
        concept_slug="count-pigeon",
    ),
    GoldenCase(
        name="aime-combinatorics",
        query="AIME combinatorics problems",
        concept_slug="count",
        competition="AIME",
    ),
]
