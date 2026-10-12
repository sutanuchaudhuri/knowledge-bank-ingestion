"""Hourly, lighter-weight mastery-only update (requirements/57 §2
`mastery_update_hourly`) — a subset of feature_refresh.py's work, run more frequently so
mastery estimates don't go stale for a full day between runs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone


def run(*, as_of_time: datetime) -> None:
    """TODO (requirements/57 §2): recompute only the mastery/transfer/hint feature group
    (features.mastery_features), not the full feature set — this is explicitly a lighter
    job than feature_refresh_daily, not a duplicate of it."""
    raise NotImplementedError("requirements/57 §2 — mastery_update_hourly")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-time", type=datetime.fromisoformat,
                         default=datetime.now(timezone.utc))
    args = parser.parse_args()
    run(as_of_time=args.as_of_time)


if __name__ == "__main__":
    main()
