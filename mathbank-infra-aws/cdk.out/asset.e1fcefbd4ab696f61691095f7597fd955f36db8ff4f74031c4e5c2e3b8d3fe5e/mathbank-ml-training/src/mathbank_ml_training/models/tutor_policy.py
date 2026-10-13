"""Tutor action policy: supervised scorer -> contextual bandit -> offline RL
(requirements/11, requirements/01 §5, requirements/55 §6).

requirements/11 §1 maturity path (reproduced here so the stage-ordering rule lives next
to the code that must enforce it, not only in a markdown file):

    Stage 0: deterministic authored tutor     (already in production — mathbank-agent)
    Stage 1: supervised scoring / imitation
    Stage 2: contextual bandit for approved action selection
    Stage 3: offline RL over approved actions
    Stage 4: controlled online experimentation
    Stage 5: optional LLM fine-tuning from approved preference data

"Never start with unrestricted online RL against real students" (requirements/11 §1).
"""
from __future__ import annotations

from typing import Literal

Stage = Literal[0, 1, 2, 3, 4, 5]

# TODO: as each stage is actually implemented, bump this constant. Keep it a single
# source of truth so `train()` below can refuse to run a stage beyond what exists yet.
HIGHEST_IMPLEMENTED_STAGE: Stage = 0  # Stage 0 (deterministic authored tutor) already
                                       # exists in mathbank-agent; nothing in *this*
                                       # package implements it, it's listed here only so
                                       # the stage numbering has a correct starting point.


class TutorPolicyModel:
    """Chooses an action ID from an already-action-masked set (requirements/11 §6 —
    masking happens *before* this class ever sees the candidates; this class must never
    itself decide which actions are "allowed", only rank/score among them).
    """

    def train(self, dataset: dict, *, stage: Stage) -> None:
        """TODO (requirements/55 §6): implement stage 1 (supervised action scorer) first.
        This function intentionally raises for any `stage` beyond
        HIGHEST_IMPLEMENTED_STAGE so a future caller cannot accidentally skip ahead to
        offline RL before imitation learning has ever been validated.
        """
        if stage > HIGHEST_IMPLEMENTED_STAGE:
            raise NotImplementedError(
                f"requirements/55 §6 / requirements/11 §1 — stage {stage} is not yet "
                f"implemented (highest implemented stage is {HIGHEST_IMPLEMENTED_STAGE}); "
                "do not skip the maturity path."
            )
        raise NotImplementedError("requirements/55 §6 — tutor policy training")

    def score_actions(self, observation: dict, allowed_action_ids: list[str]) -> dict[str, float]:
        raise NotImplementedError("requirements/55 §6 — tutor policy scoring")
