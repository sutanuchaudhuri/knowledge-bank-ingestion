import json
import math
import re
import xml.etree.ElementTree as ET

import pytest
from geometry_scene.schemas import MathObject, RelationStatus, SceneInput, StateDelta, VisualDelta
from pydantic import ValidationError

from neural_geometry.cli import gallery
from neural_geometry.compiler import CompileError, compile_program
from neural_geometry.examples import examples
from neural_geometry.models import (
    AddProvisionalCurve,
    ApplyDelta,
    ConstructionProgram,
    CreateScene,
    LayoutAngle,
    MathematicalVariable,
    Present,
    TrustedFacts,
)

SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("name", list(examples()))
def test_examples_valid_repeatable_and_input_immutable(name):
    program, facts = examples()[name]
    before = program.model_dump_json()
    first = compile_program(program, facts)
    second = compile_program(ConstructionProgram.model_validate_json(before), facts)
    assert [frame.svg for frame in first] == [frame.svg for frame in second]
    assert all(frame.core.validation.valid for frame in first)
    assert [frame.core.version for frame in first] == list(range(len(first)))
    assert program.model_dump_json() == before
    assert len({frame.program_hash for frame in first}) == 1


def test_layout_angle_is_bounded_not_a_mathematical_fact():
    program, facts = examples()["01_free_intersection"]
    frame = compile_program(program, facts)[0]
    value = frame.layout_values[0]
    assert 35 <= value.degrees <= 145
    assert not frame.core.math_state.relations
    points = frame.core.scene_state.entities
    a, p, b = (points["point_" + name] for name in ("A", "P", "B"))
    u, v = (a.x - p.x, a.y - p.y), (b.x - p.x, b.y - p.y)
    actual = math.degrees(
        math.acos((u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v)))
    )
    assert actual == pytest.approx(value.degrees)
    assert value.source == "LAYOUT_ONLY"


def test_provisional_curve_never_asserts_circle_or_changes_math():
    program, facts = examples()["02_provisional_curve"]
    initial, guide = compile_program(program, facts)
    assert initial.core.math_state.relations == guide.core.math_state.relations
    assert guide.core.math_state.relations[0].status == RelationStatus.TARGET_TO_PROVE
    root = ET.fromstring(guide.svg)
    path = root.find(f".//{SVG}path[@id='gamma']")
    assert path is not None
    assert path.attrib["data-semantic-type"] == "PROVISIONAL_CURVE"
    assert path.attrib["stroke-dasharray"] == "5 5"
    assert " C " in path.attrib["d"] and " A " not in path.attrib["d"]
    assert not path.attrib["d"].endswith("Z")
    numbers = [
        float(value) for value in re.findall(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", path.attrib["d"])
    ]
    endpoints = [(numbers[0], numbers[1])]
    endpoints.extend(
        (numbers[index + 4], numbers[index + 5]) for index in range(2, len(numbers), 6)
    )
    expected_points = [
        guide.core.scene_state.entities["point_" + name] for name in ("A", "B", "C", "D")
    ]
    assert endpoints == [(point.x, point.y) for point in expected_points]
    assert not any(
        entity.type in {"CIRCLE", "ARC"} for entity in guide.core.scene_state.entities.values()
    )


def test_trusted_promotion_changes_semantics_and_retains_history():
    program, facts = examples()["03_trusted_circle_promotion"]
    frames = compile_program(program, facts)
    assert len(frames[1].curves) == 1 and not frames[2].curves
    assert frames[1].core.math_state.relations[0].status == RelationStatus.TARGET_TO_PROVE
    assert frames[2].core.math_state.relations[0].status == RelationStatus.PROVEN
    assert frames[2].replacements[0].circle_id == "circle_cyclic"
    assert ET.fromstring(frames[2].svg).find(f".//{SVG}path[@id='gamma']") is None
    assert "circle_cyclic" in frames[2].core.scene_state.entities
    assert frames[2].core.validation.residuals["cyclic"] < 1e-6
    assert set(frames[0].core.math_state.objects) == set(frames[-1].core.math_state.objects)


def test_model_cannot_authorize_own_proof():
    program, _ = examples()["03_trusted_circle_promotion"]
    with pytest.raises(CompileError, match="trusted concyclicity") as error:
        compile_program(program)
    assert error.value.step == 2 and error.value.code == "UNTRUSTED_FACT"


def test_untrusted_proof_cannot_bypass_promotion_through_raw_delta():
    program, facts = examples()["03_trusted_circle_promotion"]
    bypass = program.model_copy(
        update={
            "steps": (
                program.steps[0],
                ApplyDelta(
                    delta=StateDelta(
                        expected_version=0,
                        add_relations=(facts.relations[0],),
                        relayout=True,
                    )
                ),
            )
        }
    )
    with pytest.raises(CompileError, match="exact trusted evidence"):
        compile_program(bypass)


def test_proof_for_wrong_points_is_rejected():
    program, facts = examples()["03_trusted_circle_promotion"]
    wrong = facts.relations[0].model_copy(update={"args": ("A", "B", "C")})
    with pytest.raises(CompileError, match="matching trusted"):
        compile_program(program, TrustedFacts(relations=(wrong,)))


def test_promotion_cannot_silently_move_previous_points():
    program, facts = examples()["03_trusted_circle_promotion"]
    operation = program.steps[2].model_copy(update={"relayout": False})
    fixed = program.model_copy(update={"steps": (*program.steps[:2], operation)})
    with pytest.raises(CompileError):
        compile_program(fixed, facts)


@pytest.mark.parametrize("name", ["Absent", "A"])
def test_provisional_curve_cannot_reveal_absent_or_hidden_points(name):
    program, _ = examples()["02_provisional_curve"]
    hidden = Present(visual=VisualDelta(hide=("point_A",)))
    curve = AddProvisionalCurve(id="guide", through=(name, "B", "C"))
    modified = program.model_copy(update={"steps": (program.steps[0], hidden, curve)})
    with pytest.raises(CompileError, match="absent/hidden"):
        compile_program(modified)


def test_namespace_collision_does_not_become_given_angle():
    program, _ = examples()["01_free_intersection"]
    initial = program.steps[0]
    collision = initial.model_copy(
        update={
            "mathematical_variables": (
                MathematicalVariable(name="theta_layout", meaning="math angle", unit="DEGREES"),
            )
        }
    )
    with pytest.raises(CompileError, match="namespaces"):
        compile_program(program.model_copy(update={"steps": (collision,)}))


def test_layout_cannot_overwrite_existing_position():
    program, _ = examples()["01_free_intersection"]
    initial = program.steps[0]
    scene = initial.scene.model_copy(update={"positions": {"P": (320, 240)}})
    with pytest.raises(CompileError, match="overwrite"):
        compile_program(
            program.model_copy(update={"steps": (initial.model_copy(update={"scene": scene}),)})
        )


def test_curve_cannot_be_reintroduced_after_promotion():
    program, facts = examples()["03_trusted_circle_promotion"]
    repeated = program.model_copy(update={"steps": (*program.steps, program.steps[1])})
    with pytest.raises(CompileError, match="cannot be reused"):
        compile_program(repeated, facts)


def test_presentation_cannot_hide_required_provisional_points():
    program, facts = examples()["02_provisional_curve"]
    hidden = program.model_copy(
        update={
            "steps": (
                *program.steps,
                Present(visual=VisualDelta(hide=("point_B",))),
            )
        }
    )
    with pytest.raises(CompileError, match="absent/hidden"):
        compile_program(hidden, facts)


def test_stale_delta_and_scene_reset_are_rejected():
    program, _ = examples()["02_provisional_curve"]
    stale = program.model_copy(
        update={
            "steps": (
                *program.steps,
                ApplyDelta(delta=StateDelta(expected_version=0)),
            )
        }
    )
    with pytest.raises(CompileError, match="expected version"):
        compile_program(stale)
    with pytest.raises(ValidationError, match="reset"):
        ConstructionProgram(id="reset", steps=(program.steps[0], program.steps[0]))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"minimum": 90, "maximum": 60},
        {"preference": float("nan")},
        {"points": ("A", "A", "B")},
    ],
)
def test_invalid_layout_contracts(kwargs):
    values = {"name": "theta_layout", "points": ("A", "P", "B"), **kwargs}
    with pytest.raises(ValidationError):
        LayoutAngle(**values)


def test_gallery_persists_every_frame_and_replay_program(tmp_path):
    result = gallery(tmp_path)
    assert result["cases"] == 3 and result["frames"] == 8
    assert len(list(tmp_path.glob("*/frame_*.svg"))) == 8
    for directory in (path for path in tmp_path.iterdir() if path.is_dir()):
        program = ConstructionProgram.model_validate_json((directory / "program.json").read_text())
        facts = TrustedFacts.model_validate_json((directory / "trusted_facts.json").read_text())
        frames = compile_program(program, facts)
        assert (directory / "frame_000.svg").read_text().strip() == frames[0].svg
        assert json.loads((directory / "report.json").read_text())["valid"]


def test_unknown_operation_and_embedded_trust_are_invalid():
    initial = CreateScene(scene=SceneInput(objects={"A": {}, "B": {}, "C": {}}))
    document = {
        "id": "bad",
        "steps": [initial.model_dump(mode="json"), {"op": "PROVE", "source": "the model says so"}],
    }
    with pytest.raises(ValidationError):
        ConstructionProgram.model_validate(document)
    document = {
        "id": "bad",
        "steps": [initial.model_dump(mode="json")],
        "trusted_facts": {"relations": []},
    }
    with pytest.raises(ValidationError):
        ConstructionProgram.model_validate(document)


@pytest.mark.parametrize("identifier", ["base", "scene_title", "point_A"])
def test_provisional_curve_cannot_collide_with_rendered_ids(identifier):
    program, _ = examples()["02_provisional_curve"]
    operation = program.steps[1].model_copy(update={"id": identifier})
    with pytest.raises(CompileError, match="duplicate visual"):
        compile_program(program.model_copy(update={"steps": (program.steps[0], operation)}))


def test_normalized_program_hash_is_independent_of_dictionary_order():
    program, facts = examples()["02_provisional_curve"]
    document = json.loads(json.dumps(program.model_dump(mode="json"), sort_keys=True))
    reordered = ConstructionProgram.model_validate(document)
    assert (
        compile_program(program, facts)[0].program_hash
        == compile_program(reordered, facts)[0].program_hash
    )


def test_cli_invalid_program_reports_failure_without_publishing(tmp_path, monkeypatch, capsys):
    from neural_geometry.cli import main

    program, _ = examples()["03_trusted_circle_promotion"]
    path = tmp_path / "untrusted.json"
    path.write_text(program.model_dump_json())
    output = tmp_path / "rejected"
    monkeypatch.setattr(
        "sys.argv", ["neural-geometry", "compile", str(path), "--output", str(output)]
    )
    assert main() == 1
    report = json.loads(capsys.readouterr().out)
    assert not report["valid"] and report["code"] == "UNTRUSTED_FACT"
    assert report["step"] == 2
    assert not output.exists()


def test_disjoint_layout_angles_use_separate_regions():
    program, _ = examples()["01_free_intersection"]
    initial = program.steps[0]
    scene = initial.scene.model_copy(
        update={
            "objects": {
                **initial.scene.objects,
                **{name: MathObject() for name in ("C", "Q", "D")},
            },
        }
    )
    operation = initial.model_copy(
        update={
            "scene": scene,
            "layout_variables": (
                *initial.layout_variables,
                LayoutAngle(
                    name="second_layout_angle",
                    points=("C", "Q", "D"),
                ),
            ),
        }
    )
    frame = compile_program(program.model_copy(update={"steps": (operation,)}))[0]
    assert frame.core.validation.valid
    assert len(frame.layout_values) == 2
    assert (
        frame.core.scene_state.entities["point_P"].x != frame.core.scene_state.entities["point_Q"].x
    )
    assert not frame.core.math_state.relations


def test_trusted_proof_without_provenance_is_invalid():
    _, facts = examples()["03_trusted_circle_promotion"]
    relation = facts.relations[0].model_copy(update={"provenance": ""})
    with pytest.raises(ValidationError, match="provenance"):
        TrustedFacts(relations=(relation,))
