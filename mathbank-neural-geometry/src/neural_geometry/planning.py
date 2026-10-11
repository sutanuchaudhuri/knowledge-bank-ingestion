from __future__ import annotations

from .compiler import CompileError, compile_program
from .models import (
    CompiledFrame,
    ConstructionProgram,
    PlanningInput,
    ProgramPlanner,
    TrustedFacts,
    VisualCritic,
)


class PlanningFailure(ValueError):
    def __init__(self, attempts: tuple[dict, ...]):
        super().__init__("No reviewed construction program accepted within the attempt budget")
        self.attempts = attempts


def plan_and_compile(
    request: PlanningInput,
    planner: ProgramPlanner,
    critic: VisualCritic,
    trusted_facts: TrustedFacts | None = None,
    max_attempts: int = 3,
) -> tuple[ConstructionProgram, tuple[CompiledFrame, ...], tuple[dict, ...]]:
    """Provider-neutral bounded loop. Provider failures propagate rather than becoming success."""
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")
    attempts: list[dict] = []
    feedback: tuple[str, ...] = ()
    for number in range(1, max_attempts + 1):
        program = planner.plan(request, feedback)
        if not isinstance(program, ConstructionProgram):
            raise TypeError("planner must return a validated ConstructionProgram")
        if request.previous_program and (
            program.steps[: len(request.previous_program.steps)] != request.previous_program.steps
        ):
            feedback = ("Planner must preserve the exact accepted program prefix.",)
            attempts.append(
                {
                    "attempt": number,
                    "status": "COMPILE_REJECTED",
                    "code": "HISTORY_CHANGED",
                    "findings": feedback,
                }
            )
            continue
        try:
            frames = compile_program(program, trusted_facts)
        except CompileError as exc:
            feedback = (str(exc),)
            attempts.append(
                {
                    "attempt": number,
                    "status": "COMPILE_REJECTED",
                    "code": exc.code,
                    "step": exc.step,
                    "findings": feedback,
                }
            )
            continue
        findings: list[str] = []
        for frame in frames:
            report = critic.review(request, frame)
            if not report.accepted:
                findings.extend(report.findings or (f"critic rejected step {frame.step}",))
        if findings:
            feedback = tuple(findings[:32])
            attempts.append({"attempt": number, "status": "CRITIC_REJECTED", "findings": feedback})
            continue
        attempts.append(
            {"attempt": number, "status": "ACCEPTED", "program_hash": frames[-1].program_hash}
        )
        return program, frames, tuple(attempts)
    raise PlanningFailure(tuple(attempts))
