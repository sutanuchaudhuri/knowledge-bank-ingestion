"""Daily data-readiness scan job (requirements/57 §2 `data_readiness_daily`,
requirements/09, requirements/58 §3).

Produces `ml.data_quality_issue` rows and the ranked "what data should improve?" admin
report (requirements/09 §8).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone


def run(*, as_of_time: datetime) -> None:
    """TODO (requirements/57 §2, requirements/09 §2): check each quality dimension
    (COVERAGE, RECENCY, VOLUME, BALANCE, CONSISTENCY, LABEL_QUALITY, TIMESTAMP_QUALITY,
    GRAPH_MAPPING, DIFFICULTY_CALIBRATION, DUPLICATION, LEAKAGE_RISK) per student and per
    content item, writing contracts.DataQualityIssue rows. Never auto-mutate canonical
    metadata (requirements/09 §6) — this job only ever proposes."""
    raise NotImplementedError("requirements/57 §2 — data_readiness_daily")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-time", type=datetime.fromisoformat,
                         default=datetime.now(timezone.utc))
    args = parser.parse_args()
    run(as_of_time=args.as_of_time)


if __name__ == "__main__":
    main()
