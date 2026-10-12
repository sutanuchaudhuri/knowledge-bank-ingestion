"""Daily tutor-trajectory export job (requirements/57 §2
`tutor_policy_dataset_daily`) — exports `ml.tutor_trajectory`/`ml.tutor_turn` rows as a
training-ready dataset for the next tutor-policy training run (requirements/55 §6).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone


def run(*, as_of_time: datetime) -> None:
    """TODO (requirements/57 §2): export REAL + SIMULATED trajectories separately
    (contracts.TutorTrajectory.source) — requirements/16 invariant #10: "synthetic
    trajectories stay labeled and weighted separately," never silently merged with real
    ones."""
    raise NotImplementedError("requirements/57 §2 — tutor_policy_dataset_daily")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of-time", type=datetime.fromisoformat,
                         default=datetime.now(timezone.utc))
    args = parser.parse_args()
    run(as_of_time=args.as_of_time)


if __name__ == "__main__":
    main()
