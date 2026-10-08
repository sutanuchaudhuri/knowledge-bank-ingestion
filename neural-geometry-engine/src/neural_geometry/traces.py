from __future__ import annotations

from .compiler import program_hash
from .models import CompiledFrame, ConstructionProgram, PlanningInput


def training_record(
    request: PlanningInput,
    program: ConstructionProgram,
    frames: tuple[CompiledFrame, ...],
    *,
    approved_for_training: bool,
    source_id: str,
    license_id: str,
) -> dict:
    """Explicit local export of reviewed examples, without provider/debug/solver internals."""
    if not approved_for_training:
        raise ValueError("training export requires explicit data-use approval")
    if not source_id.strip() or not license_id.strip():
        raise ValueError("training export requires source and license identifiers")
    if len(frames) != len(program.steps) or not all(
        frame.core.validation.valid for frame in frames
    ):
        raise ValueError("training export requires the complete accepted frame sequence")
    expected_hash = program_hash(program)
    if any(
        frame.program_hash != expected_hash or frame.step != index
        for index, frame in enumerate(frames)
    ):
        raise ValueError("training frames do not belong to this program")
    return {
        "record_version": "nge-training-1",
        "data_use": {"approved": True, "source_id": source_id, "license_id": license_id},
        "input": request.model_dump(mode="json"),
        "target": program.model_dump(mode="json"),
        "frames": [
            {
                "step": frame.step,
                "program_hash": frame.program_hash,
                "math_state": frame.core.math_state.model_dump(mode="json"),
                "layout_values": [value.model_dump(mode="json") for value in frame.layout_values],
                "visual_state": frame.core.visual_state.model_dump(mode="json"),
                "provisional_curves": [curve.model_dump(mode="json") for curve in frame.curves],
                "replacements": [value.model_dump(mode="json") for value in frame.replacements],
                "validation": frame.core.validation.model_dump(mode="json"),
            }
            for frame in frames
        ],
    }
