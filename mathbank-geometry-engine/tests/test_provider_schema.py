import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from geometry_scene.openai_provider import (
    DeltaPlanOutput,
    FixedRealizationDelta,
    OpenAIProvider,
    _from_wire,
    _wire_schema,
)
from geometry_scene.orchestration import GeometryPlan
from geometry_scene.schemas import VisualDelta


def test_strict_provider_schema_maps_dynamic_dictionaries():
    schema = VisualDelta.model_json_schema()
    wire = _wire_schema(schema)
    assert wire["additionalProperties"] is False
    assert set(wire["required"]) == set(wire["properties"])
    assert wire["properties"]["styles"]["type"] == "array"
    encoded = {
        "show": [],
        "hide": [],
        "highlight": ["point_A"],
        "dim": [],
        "focus": [],
        "styles": [],
        "caption": None,
        "overlays": [],
    }
    decoded = _from_wire(encoded, schema, schema["$defs"])
    assert decoded["styles"] == {}
    assert VisualDelta.model_validate(decoded).highlight == ("point_A",)


def test_geometry_plan_wire_schema_has_no_defaults_or_dynamic_objects():
    schema = _wire_schema(GeometryPlan.model_json_schema())

    def inspect(node):
        if isinstance(node, dict):
            assert "default" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for item in node.values():
                inspect(item)
        elif isinstance(node, list):
            for item in node:
                inspect(item)

    inspect(schema)
    assert json.loads(json.dumps(schema)) == schema


def test_presentation_wire_references_only_realized_entities():
    pytest.importorskip(
        "openai", reason="Install the optional agent extra to test provider transport"
    )
    client = Mock()
    response = SimpleNamespace(
        model="test",
        usage=None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {**VisualDelta(highlight=["point_A"]).model_dump(mode="json"), "styles": []}
                    )
                )
            )
        ],
    )
    client.with_options.return_value.chat.completions.create.return_value = response
    visual = OpenAIProvider(client, "test").complete(
        "presentation",
        {"context": {"request": {}}, "available_entities": {"point_A": {}}},
        VisualDelta,
        1,
    )
    assert visual.highlight == ("point_A",)
    schema = client.with_options.return_value.chat.completions.create.call_args.kwargs[
        "response_format"
    ]["json_schema"]["schema"]
    assert schema["$defs"]["SceneEntityReference"]["enum"] == ["point_A"]
    for field in ("show", "hide", "highlight", "dim", "focus"):
        assert schema["properties"][field]["items"] == {"$ref": "#/$defs/SceneEntityReference"}


def test_fixed_delta_wire_cannot_copy_a_realization_setting():
    wire = _wire_schema(DeltaPlanOutput.model_json_schema())
    definition = wire["$defs"]["FixedRealizationDelta"]
    assert definition["properties"]["rendering_mode"]["type"] == "null"
    assert definition["properties"]["realization_seed"]["type"] == "null"
    assert FixedRealizationDelta(expected_version=0).relayout is False
