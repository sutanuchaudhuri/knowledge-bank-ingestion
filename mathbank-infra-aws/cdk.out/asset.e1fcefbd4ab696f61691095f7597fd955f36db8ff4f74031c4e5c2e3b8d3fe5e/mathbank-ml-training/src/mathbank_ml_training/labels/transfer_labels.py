"""Transfer and course-effectiveness labels (requirements/03 §3, requirements/55 §5).

requirements/03 §4 leakage rule: NEVER use future attempts/course completion to label an
earlier point in time. Every function here must take an explicit `as_of_time` and only
look *forward* from it for the outcome being labeled, never backward into training
features for the same period.
"""
from __future__ import annotations

from datetime import datetime


def label_transfer_outcome(student_id: str, target_concept_id: str, *, as_of_time: datetime,
                            horizon_days: int = 7) -> dict:
    """Future transfer-item outcome within `horizon_days` of `as_of_time` (requirements/03
    §3 "Mastery: latent/proxy labels built from future transfer items, not same-item
    correctness").

    TODO: "transfer item" needs a precise definition — likely a different problem/route
    step tagged with the same concept/technique, not a repeat of the same item. Confirm
    against the knowledge graph's existing TEACHES/APPLIES/REQUIRES edge semantics
    (already documented in this repo's graph skill materials) before implementing.
    """
    raise NotImplementedError("requirements/55 §5 — transfer label")


def label_course_lift(course_release_id: str, *, as_of_time: datetime) -> dict:
    """Course-effectiveness label: post-course held-out target performance vs. pre-course
    baseline, controlling for difficulty/selection (requirements/03 §3).

    TODO: this needs a matched-control design (requirements/08 §8) to avoid confounding
    "students who chose this course" with "the course caused improvement" — use
    associative language in any output text (contracts.InterventionEffect.summary_text's
    own TODO applies here too).
    """
    raise NotImplementedError("requirements/55 §5 — course lift label")
