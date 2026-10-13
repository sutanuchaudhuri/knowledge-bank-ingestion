"""Nightly Neo4j structural-projection refresh (requirements/57 §2/§4).

Deliberately a thin wrapper, not a reimplementation — reuses mathbank-graph's existing
`project_from_postgres.py`/`project_textbook_steps.py`. This module exists only to give
the Neo4j refresh the same nightly-scheduled entry point as the Postgres feature-refresh
job, so the two don't drift relative to each other (requirements/57 §4).

requirements/16 invariants #2/#3 apply: Neo4j stays structural/rebuildable; no
learner-specific mastery/misconception edges are ever written here.
"""
from __future__ import annotations

import argparse


def run() -> None:
    """TODO (requirements/57 §4): shell out to (or import, if mathbank-graph exposes a
    clean function boundary) mathbank-graph's project_from_postgres.py. Do not
    reimplement graph projection logic in this package. Confirm with
    GOTCHAS.md §23/§25 before running this against a non-trivial graph — the canonical
    projector's own lessons (batch per-commit, never run an unbatched rebuild, never
    interrupt an in-progress rebuild) apply here unchanged."""
    raise NotImplementedError("requirements/57 §2/§4 — graph_projection_refresh_nightly")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
