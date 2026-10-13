"""Daily feature-refresh job (requirements/57 §2 `feature_refresh_daily`).

Runnable as: `python -m mathbank_ml_training.jobs.feature_refresh --as-of-time ...`
(argparse wiring exists; the actual refresh logic is a TODO).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from mathbank_ml_training.jobs._batching import run_in_batches  # noqa: F401 (used once implemented)


def run(*, as_of_time: datetime, batch_size: int = 2000) -> None:
    """TODO (requirements/57 §2/§3): for every active student, compute
    features.mastery_features.compute_mastery_features(...) and upsert into
    `ml.feature_snapshot` via run_in_batches(), recording source_watermark on every row.
    Must be idempotent for a re-run at the same as_of_time (ON CONFLICT upsert, not
    duplicate insert)."""
    raise NotImplementedError("requirements/57 §2 — feature_refresh_daily")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-time", type=datetime.fromisoformat,
                         default=datetime.now(timezone.utc))
    parser.add_argument("--batch-size", type=int, default=2000)
    args = parser.parse_args()
    run(as_of_time=args.as_of_time, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
