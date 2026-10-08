import json

import pytest

from neural_geometry.compiler import compile_program
from neural_geometry.examples import examples
from neural_geometry.models import PlanningInput
from neural_geometry.traces import training_record


def test_local_training_trace_has_provenance_and_no_solver_debug_internals():
    program, facts = examples()["02_provisional_curve"]
    frames = compile_program(program, facts)
    request = PlanningInput(problem_text="Original synthetic points", pedagogical_goal="Guide")
    record = training_record(
        request,
        program,
        frames,
        approved_for_training=True,
        source_id="synthetic:provisional",
        license_id="project-authored",
    )
    assert record["target"]["schema_version"] == "nge-ir-1"
    assert record["frames"][1]["provisional_curves"][0]["semantic_type"] == "PROVISIONAL_CURVE"
    assert "solver_diagnostics" not in json.dumps(record)
    assert "all_positions" not in json.dumps(record)
    assert "provider" not in record


def test_export_without_consent_or_complete_sequence_fails():
    program, facts = examples()["02_provisional_curve"]
    frames = compile_program(program, facts)
    request = PlanningInput(problem_text="Points", pedagogical_goal="Guide")
    with pytest.raises(ValueError, match="data-use approval"):
        training_record(
            request,
            program,
            frames,
            approved_for_training=False,
            source_id="sample",
            license_id="project-authored",
        )
    with pytest.raises(ValueError, match="complete"):
        training_record(
            request,
            program,
            frames[:1],
            approved_for_training=True,
            source_id="sample",
            license_id="project-authored",
        )


def test_export_rejects_wrong_program_frames():
    program, _ = examples()["02_provisional_curve"]
    different, facts = examples()["01_free_intersection"]
    request = PlanningInput(problem_text="Points", pedagogical_goal="Guide")
    with pytest.raises(ValueError, match="belong"):
        training_record(
            request,
            program,
            compile_program(different, facts),
            approved_for_training=True,
            source_id="sample",
            license_id="project-authored",
        )
