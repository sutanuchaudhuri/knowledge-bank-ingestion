"""Fluid widget layer: registry/validator/composer, LaTeX formatter, authoring parser and route guards.

Pure tests — no database or model calls.
"""
from __future__ import annotations

import copy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mathbank_rest import authoring, live_runtime, math_format, security, widgets
from mathbank_rest.main import app

client = TestClient(app)


# ---------------------------------------------------------------- widget validation

def test_every_composer_strategy_produces_a_valid_spec():
    cases = [("power of a point", {}), ("intersecting chords", {}), ("triangle", {}),
             ("progress", {"steps": [{"label": "a"}, {"label": "b"}]}),
             ("anything", {"rows": [[1, 2]], "columns": ["x", "y"]}), ("unknown thing", {}),
             ("poll", {"aggregate": {"option_counts": {"A": 2, "B": 1}, "option_percentages": {"A": 66.7, "B": 33.3},
                                     "response_count": 3}, "prompt": "Q?"})]
    strategies = set()
    for intent, ctx in cases:
        out = widgets.compose(intent, ctx)
        strategies.add(out["strategy"])
        result = widgets.validate(out["spec"])
        assert result["valid"], (intent, result["errors"])
    assert {"TEMPLATE", "STEP_PROGRESS", "TABLE", "FALLBACK_FORMULA", "POLL_AGGREGATE"} <= strategies


@pytest.mark.parametrize("mutation", [
    lambda s: s["config"].update({"script": "alert(1)"}),
    lambda s: s["config"].update({"caption": "<img src=x onerror=alert(1)>"}),
    lambda s: s["config"].update({"caption": "javascript:alert(1)"}),
    lambda s: s["config"].update({"caption": r"$\href{http://x}{y}$"}),
    lambda s: s.update({"widget_type": "IFRAME"}),
    lambda s: s.update({"html": "<b>x</b>"}),
])
def test_validator_rejects_executable_or_unknown_content(mutation):
    spec = copy.deepcopy(widgets.compose("power of a point")["spec"])
    mutation(spec)
    assert not widgets.validate(spec)["valid"]


def test_validator_rejects_dangling_geometry_references():
    spec = copy.deepcopy(widgets.compose("intersecting chords")["spec"])
    spec["config"]["elements"].append({"id": "bad", "kind": "SEGMENT", "from": "A", "to": "NOPE"})
    result = widgets.validate(spec)
    assert not result["valid"] and any("NOPE" in e for e in result["errors"])


def test_validator_hides_solution_content_from_students():
    spec = widgets.compose("unknown")["spec"]
    spec["data_refs"] = {"solution_hidden": True}
    assert any("solution" in e for e in widgets.validate(spec, audience="STUDENT")["errors"])


def test_live_operations_must_target_declared_elements():
    spec = widgets.compose("power of a point")["spec"]
    known = spec["config"]["elements"][0]["id"]
    assert widgets.validate_operations(spec, [{"op": "HIGHLIGHT", "targets": [known]}]) == []
    assert widgets.validate_operations(spec, [{"op": "HIGHLIGHT", "targets": ["ghost"]}])


def test_content_hash_is_stable():
    spec = widgets.compose("triangle")["spec"]
    assert widgets.content_hash(spec) == widgets.content_hash(copy.deepcopy(spec))


# ---------------------------------------------------------------- LaTeX formatter

def test_deterministic_formatter_wraps_and_converts():
    out = math_format.deterministic_format("Since PA*PB = PC*PD, we get PA = 12/3 = 4.")
    assert r"\cdot" in out and r"\frac{12}{3}" in out and out.count("$") % 2 == 0


def test_formatter_leaves_existing_latex_alone():
    src = r"We know $\angle ABC = 90^\circ$."
    assert math_format.deterministic_format(src) == src


def test_check_latex_flags_unsafe_and_unbalanced():
    assert math_format.check_latex(r"$\href{x}{y}$")
    assert math_format.check_latex(r"$\frac{1}{2$")
    assert math_format.check_latex("$x") and not math_format.check_latex("$x$")


def test_agentic_mode_falls_back_when_model_loses_words():
    out = math_format.format_math("PA times PB equals 12", "agentic", agent=lambda t: "$12$")
    assert out["engine"] == "deterministic"


def test_agentic_mode_accepts_faithful_rewrite():
    out = math_format.format_math("PA times PB equals 12", "agentic",
                                  agent=lambda t: r"$PA$ times $PB$ equals $12$")
    assert out["engine"] != "deterministic" and "PA" in out["formatted"]


def test_agentic_mode_falls_back_on_model_error():
    def boom(_):
        raise RuntimeError("no network")
    assert math_format.format_math("x^2", "agentic", agent=boom)["engine"] == "deterministic"


# ---------------------------------------------------------------- authoring parser

PLAN = {"title": "Power of a point", "course_limit_seconds": 1800, "interaction_buffer_seconds": 120,
        "hard_limit": True, "topics": [
            {"ordinal": 0, "title": "Secants", "planned_seconds": 600, "required": True, "scenes": []},
            {"ordinal": 1, "title": "Chords", "planned_seconds": 600, "required": False, "scenes": []}]}


@pytest.mark.parametrize(("message", "op"), [
    ("set topic 2 to 8 minutes", "UPDATE_TOPIC_TIME"), ("add 5 minutes to topic 1", "UPDATE_TOPIC_TIME"),
    ("make topic 2 optional", "SET_TOPIC_REQUIRED"), ("add a poll to topic 1", "ADD_SCENE"),
    ("set the course limit to 40 minutes", "UPDATE_COURSE_LIMIT"), ("add a 5 minute buffer", "UPDATE_BUFFER"),
    ('add a topic "Tangents" for 5 minutes', "ADD_TOPIC"), ("move topic 2 to first", "MOVE_TOPIC"),
    ("remove topic 2", "REMOVE_TOPIC"),
])
def test_admin_chat_messages_compile_to_patch_operations(message, op):
    ops, summary = authoring.parse_admin_message(message, PLAN)
    assert ops and ops[0]["op"] == op and summary


def test_unknown_message_yields_no_patch():
    assert authoring.parse_admin_message("hello there", PLAN)[0] == []


def test_over_budget_patch_is_invalid_under_hard_limit_and_alternative_funds_it():
    ops, _ = authoring.parse_admin_message("add 10 minutes to topic 1", PLAN)
    after = authoring.apply_operations(PLAN, ops)
    assert not authoring.validate_plan(after)["valid"]
    alt = authoring.alternative_operations(PLAN, ops)
    assert alt and authoring.validate_plan(authoring.apply_operations(PLAN, alt))["valid"]


def test_apply_operations_does_not_mutate_input():
    snapshot = copy.deepcopy(PLAN)
    authoring.apply_operations(PLAN, authoring.parse_admin_message("remove topic 2", PLAN)[0])
    assert PLAN == snapshot


# ---------------------------------------------------------------- live pure logic

def test_instructor_nl_compiles_polls_with_options_and_answer():
    acts = live_runtime.compile_instructor_command(
        "open poll: Which equals PA·PB? A) PC·PD B) PC+PD C) PO² correct is A", {})
    definition = acts[0]["payload"]["definition"]
    assert [o["key"] for o in definition["options"]] == ["A", "B", "C"]
    assert definition["options"][0]["label"] == "PC·PD"
    assert definition["correctness_policy"] == {"correct_option": "A"}


@pytest.mark.parametrize(("message", "command"), [
    ("next", "NEXT"), ("extend 5 minutes", "EXTEND"), ("skip topic 3", "SKIP"), ("take over", "TAKEOVER"),
    ("lock the agent", "LOCK_AGENT"), ("reveal results", "REVEAL_ACTIVITY"), ("go to topic 2", "FORCE_SCENE"),
    ("show power of a point", "SHOW_WIDGET"), ("pause", "PAUSE"), ("hand back to the AI", "RELEASE"),
])
def test_instructor_nl_commands(message, command):
    assert live_runtime.compile_instructor_command(message, {})[0]["command_type"] == command


def test_time_state_recommends_skipping_optional_topics_when_behind():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    s = {"started_at": now - timedelta(minutes=25), "topic_started_at": now - timedelta(minutes=25),
         "status": "ACTIVE", "course_limit_seconds": 1800, "extension_seconds": 0, "hard_limit": True,
         "current_topic_index": 0, "paused_total_seconds": 0,
         "topics": [{"ordinal": 0, "title": "A", "planned_seconds": 600, "required": True},
                    {"ordinal": 1, "title": "B", "planned_seconds": 600, "required": False}]}
    t = live_runtime.time_state(s, now)
    assert t["status"] == "BEHIND"
    assert t["recommendations"][0]["action"]["command_type"] == "SKIP"
    assert all(r["action"]["command_type"] != "EXTEND" for r in t["recommendations"])  # hard limit


# ---------------------------------------------------------------- route guards (no DB access)

def test_registry_is_public_and_lists_types():
    body = client.get("/v1/widgets/registry").json()
    assert {"GEOMETRY_DIAGRAM", "POLL_RESULT", "FORMULA_CARD"} <= {w["widget_type"] for w in body["widget_types"]}


@pytest.mark.parametrize(("method", "path"), [
    ("post", "/v1/tutor/format-math"), ("post", "/v1/widgets/generate"), ("get", "/v1/authoring/presentation-plans"),
    ("post", "/v1/live/sessions"), ("get", "/v1/live/sessions/x/state"), ("post", "/v1/live/sessions/x/commands"),
    ("get", "/v1/tutor/sessions/x/context"), ("post", "/v1/instructor/live/x/commands"),
])
def test_fluid_and_live_routes_require_credentials(method, path):
    kw = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(path, **kw).status_code in (401, 422)
    assert getattr(client, method)(path, headers={"X-Admin-Api-Key": "wrong"}, **kw).status_code in (401, 422)


def test_student_can_format_math_without_database():
    token = security.create_access_token(uuid4())
    r = client.post("/v1/tutor/format-math", json={"text": "PA*PB = 12"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["engine"] == "deterministic" and r"\cdot" in r.json()["formatted"]


def test_student_cannot_use_staff_live_routes():
    token = security.create_access_token(uuid4())
    r = client.post("/v1/live/sessions", json={"title": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_format_fixtures_shared_with_js_mirror():
    """mathbank-widgets/src/format.mjs mirrors math_format; both suites check the same fixtures."""
    import json
    from pathlib import Path

    from mathbank_rest.math_format import check_latex, deterministic_format

    path = Path(__file__).resolve().parents[2] / "mathbank-widgets" / "fixtures" / "format_cases.json"
    if not path.exists():
        pytest.skip("mathbank-widgets fixtures not present")
    for case in json.loads(path.read_text()):
        if case.get("check_only"):
            assert check_latex(case["input"]) == case["warnings"], case["input"]
        else:
            assert deterministic_format(case["input"]) == case["formatted"], case["input"]
            assert check_latex(case["formatted"]) == case["warnings"]


def test_unknown_activity_type_is_rejected_before_the_database():
    """Unknown types used to reach the CHECK constraint and surface as a 500; they are a 422 now."""
    with pytest.raises(live_runtime.LiveError) as err:
        live_runtime.create_activity_definition(None, {"activity_type": "POLL", "prompt": "Q",
                                                       "options": [{"id": "A"}, {"id": "B"}]}, "instructor:t")
    assert (err.value.status_code, err.value.code) == (422, "ACTIVITY_INVALID")
    assert "LIVE_POLL" in str(err.value)


def test_student_may_compose_widgets_but_not_store_them():
    token = security.create_access_token(uuid4())
    headers = {"Authorization": "Bearer " + token}
    r = client.post("/v1/widgets/generate", json={"intent": "power of a point", "store": True}, headers=headers)
    assert r.status_code == 403
    assert client.post("/v1/widgets/generate", json={"intent": "power of a point"}).status_code == 401
