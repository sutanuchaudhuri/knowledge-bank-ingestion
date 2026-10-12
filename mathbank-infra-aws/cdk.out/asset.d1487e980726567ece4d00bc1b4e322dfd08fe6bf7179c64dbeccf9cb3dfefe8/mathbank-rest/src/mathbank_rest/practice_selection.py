"""Versioned fit scoring inside an already validated mathematical candidate set."""

from __future__ import annotations

import json
from pathlib import Path

PROFILE_PATH = Path(__file__).with_name("practice_profiles.json")


def load_profile(version: str = "topic-fit-v1") -> dict:
    profiles = json.loads(PROFILE_PATH.read_text())
    if version not in profiles:
        raise ValueError(f"Unknown practice profile: {version}")
    profile = profiles[version]
    if not 0 <= profile["minimum_confidence"] <= 1 or any(
        not isinstance(value, (int, float)) or value < 0
        for value in profile["weights"].values()
    ) or not sum(profile["weights"].values()):
        raise ValueError("Invalid practice profile weights/confidence")
    return profile


def rank_candidates(candidates: list[dict], *, profile: dict, limit: int,
                    target_difficulty: int | None = None, known_skills: list[str] | None = None,
                    exposed_codes: list[str] | None = None, exclude_codes: list[str] | None = None) -> list[dict]:
    """Greedy diversity ranking; unknown telemetry remains null, not perfect fit."""
    weights = profile["weights"]
    known = set(known_skills or [])
    exposed = set(exposed_codes or [])
    excluded = set(exclude_codes or [])
    remaining = [
        c for c in candidates if c["canonical_code"] not in excluded
        and float(c["confidence"]) >= profile["minimum_confidence"]
    ]
    selected = []
    structures: set[str] = set()
    while remaining and len(selected) < limit:
        scored = []
        for candidate in remaining:
            skills = set(candidate.get("skill_ids") or [])
            gaps = candidate.get("gap_skill_ids")
            prerequisites = set(candidate.get("prerequisite_ids") or [])
            difficulty = candidate.get("difficulty")
            structure = candidate.get("structure_key")
            signals = {
                "skill_match": 1.0 if candidate["node_type"] == "SKILL" else None,
                "technique_match": 1.0 if candidate["node_type"] == "TECHNIQUE" else None,
                "prerequisite_fit": len(prerequisites & known) / len(prerequisites) if prerequisites and known else None,
                "difficulty_fit": max(0, 1 - abs(difficulty - target_difficulty) / 4)
                if difficulty is not None and target_difficulty is not None else None,
                "misconception_relevance": float(bool(skills & set(gaps)))
                if gaps is not None else None,
                "structural_diversity": float(structure not in structures) if structure else None,
                "semantic_similarity": None,
                "previous_exposure": float(candidate["canonical_code"] not in exposed)
                if candidate.get("exposure_known") or exposed_codes is not None else None,
            }
            score = sum(weights[key] * value for key, value in signals.items() if value is not None)
            scored.append({**candidate, "signals": signals, "score": round(score, 6),
                           "unknown_signals": [key for key, value in signals.items() if value is None]})
        scored.sort(key=lambda c: (-c["score"], -float(c["confidence"]), c["canonical_code"]))
        choice = scored[0]
        selected.append(choice)
        if choice.get("structure_key"):
            structures.add(choice["structure_key"])
        remaining = [c for c in remaining if c["canonical_code"] != choice["canonical_code"]]
    return selected
