"""Opt-in paid interpretation evaluation; plans are judged semantically, never by bytes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .cli import write_frame
from .openai_provider import OpenAIProvider
from .orchestration import GeometryRequest, OrchestrationFailure, orchestrate
from .schemas import SceneInput
from .service import create_scene

PARAPHRASES = {
    "01": "Connect A to C and emphasize that diagonal while keeping the quadrilateral and faint circumcircle.",
    "02": "Emphasize intersection E and draw its two construction lines, UV and WZ. The collinearity target remains unproved.",
    "03": "Make the touching point T the focus; do not add a perpendicularity assertion.",
    "04": "Bring triangles ABC and ADE into focus, leaving their similarity unproved.",
    "05": "Explain where A1 comes from: show triangle BCD and its circumcenter A1, retaining ABCD and keeping the other centers deferred.",
    "06": "Draw the straight chord joining A and B, emphasize it, and keep the circle as a local visible arc.",
    "07": "Continue AB past B to a new point E; the extension BE is dashed.",
    "08": "Drop a perpendicular from A to side BC with foot Ha; show the construction's right angle and dashed altitude.",
    "09": "Join C to midpoint M as a dashed auxiliary and make it the current focus, without losing the existing equal-half marks.",
    "10": "Emphasize the broken path X-P-Y; its straightness is not established.",
}


def evaluate(fixtures, output, provider_factory, repeats=1, cases=None, paraphrases=False):
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(fixtures.glob("*.json")):
        if cases and path.stem[:2] not in cases:
            continue
        document = json.loads(path.read_text())
        previous = create_scene(SceneInput.model_validate(document["initial"]))
        for repetition in range(repeats):
            directory = output / (path.stem + f"_run_{repetition + 1}")
            goal = (
                document.get("agent_goal")
                or {
                    "01": "Add and highlight diagonal AC, preserving ABCD and the light circle.",
                    "02": "Show the two defining auxiliary lines through E, highlight E; do not prove collinearity.",
                    "03": "Highlight tangent contact T, do not assert a right-angle theorem yet.",
                    "04": "Highlight both triangles ABC and ADE, without asserting similarity.",
                    "05": "Help the student understand A1, the center of the circumcircle of BCD, reveal only A1.",
                    "06": "Add and highlight chord AB, preserving the local arc of the large circle.",
                    "07": "Construct E on the extension of AB beyond B and keep BE dashed.",
                    "08": "Construct altitude AHa from A to BC, with a justified right-angle mark.",
                    "09": "Draw and highlight auxiliary CM, preserve the midpoint ticks.",
                    "10": "Highlight XP and PY but do not straighten them before a proof.",
                }[path.stem[:2]]
            )
            if paraphrases:
                goal = PARAPHRASES[path.stem[:2]]
            expected = document["expected"][1]
            if path.stem.startswith("10"):
                expected = {"entities": ["segment_XP", "segment_PY"], "absent": ["line_XPY"]}
            required = tuple(expected.get("entities", []))
            forbidden = tuple(expected.get("absent", []))
            request = GeometryRequest(
                problem_text=previous.math_state.problem_text,
                goal=goal,
                scene_id=previous.scene_state.scene_id,
                expected_version=previous.version,
                required_entities=required,
                forbidden_entities=forbidden,
                context=tuple(
                    {
                        "type": "known",
                        "fact": r.provenance or f"{r.type}({','.join(r.args)}) [{r.status}]",
                    }
                    for r in previous.math_state.relations
                ),
                trusted_facts=previous.math_state.relations,
            )
            provider = provider_factory()
            try:
                frame, evidence = orchestrate(request, provider, previous)
                checks = {}
                for name in required:
                    checks["visible:" + name] = frame.visual_state.styles[name].visible
                for name in expected.get("highlight", []):
                    checks["highlight:" + name] = (
                        frame.visual_state.styles[name].emphasis == "HIGHLIGHT"
                    )
                for name in expected.get("dashed", []):
                    checks["dashed:" + name] = (
                        frame.visual_state.styles[name].line_style == "DASHED"
                    )
                for name in expected.get("arcs", []):
                    checks["arc:" + name] = (
                        frame.visual_state.styles[name].render_mode == "VISIBLE_ARC"
                    )
                checks["validation"] = frame.validation.valid
                checks["base_preserved"] = set(previous.scene_state.entities) <= set(
                    frame.scene_state.entities
                )
                if path.stem.startswith("05"):
                    definition = next(r for r in frame.math_state.relations if r.id == "def_A1")
                    checks["A1_exact_BCD"] = definition.args == ("A1", "B", "C", "D")
                    checks["later_hidden"] = all(
                        "point_" + p not in frame.scene_state.entities
                        for p in ("B1", "C1", "D1", "A2", "B2", "C2", "D2")
                    )
                valid = all(checks.values())
                evidence["semantic_checks"] = checks
                write_frame(frame, directory)
            except OrchestrationFailure as exc:
                evidence = exc.evidence
                valid = False
                directory.mkdir(parents=True, exist_ok=True)
            (directory / "agent_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
            results.append(
                {
                    "case": path.stem,
                    "repeat": repetition + 1,
                    "passed": valid,
                    "calls": evidence["calls"],
                    "model": provider.model,
                }
            )
            print(
                json.dumps(
                    {
                        "case": path.stem,
                        "repeat": repetition + 1,
                        "passed": valid,
                        "calls": evidence["calls"],
                    }
                ),
                flush=True,
            )
    summary = {
        "evaluated": len(results),
        "passed": sum(r["passed"] for r in results),
        "failed": sum(not r["passed"] for r in results),
        "results": results,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def evaluate_probes(output, provider_factory):
    output.mkdir(parents=True, exist_ok=True)
    definitions = (
        "ABCD is a convex quadrilateral. A1 is the circumcenter of triangle BCD. "
        "B1 is the circumcenter of triangle CDA. C1 is the circumcenter of triangle DAB. "
        "D1 is the circumcenter of triangle ABC."
    )
    probes = [
        (
            "initial_a1",
            GeometryRequest(
                problem_text=definitions,
                goal="Help the student understand A1; no later centers.",
                required_entities=("quadrilateral_ABCD", "triangle_BCD", "point_A1"),
                forbidden_entities=("point_B1", "point_C1", "point_D1"),
            ),
            True,
        ),
        (
            "initial_a1_paraphrase",
            GeometryRequest(
                problem_text=definitions.replace(
                    "circumcenter of triangle", "center of the circumcircle of"
                ),
                goal="Focus on A1 and the three points defining its circumcircle; preserve ABCD.",
                required_entities=("quadrilateral_ABCD", "triangle_BCD", "point_A1"),
                forbidden_entities=("point_B1", "point_C1", "point_D1"),
            ),
            True,
        ),
        (
            "ambiguous_center",
            GeometryRequest(
                problem_text="ABC and DEF are two unrelated triangles.",
                goal="Draw its center, using exact source facts only; do not guess which triangle or center.",
            ),
            False,
        ),
        (
            "unsupported_geometry",
            GeometryRequest(
                problem_text="No Euclidean geometry facts are supplied.",
                goal="Construct an exact four-dimensional hyperbolic polytope, not a two-dimensional schematic.",
            ),
            False,
        ),
        (
            "target_as_given",
            GeometryRequest(
                problem_text="Prove A, B, C are collinear.",
                goal="Declare the collinearity proven from this statement alone.",
            ),
            False,
        ),
    ]
    results = []
    for name, request, should_accept in probes:
        provider = provider_factory()
        directory = output / name
        directory.mkdir(parents=True, exist_ok=True)
        try:
            frame, evidence = orchestrate(request, provider)
            checks = {
                "expected_acceptance": should_accept,
                "valid": frame.validation.valid,
            }
            if should_accept:
                checks["exact_A1_BCD"] = any(
                    r.type == "CIRCUMCENTER" and r.args == ("A1", "B", "C", "D")
                    for r in frame.math_state.relations
                )
            write_frame(frame, directory)
            accepted = True
        except OrchestrationFailure as exc:
            evidence = exc.evidence
            accepted = False
            checks = {
                "expected_rejection": not should_accept,
                "paid_model_called": evidence["calls"] > 0,
            }
        evidence["semantic_checks"] = checks
        (directory / "agent_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        result = {
            "case": name,
            "passed": all(checks.values()),
            "accepted": accepted,
            "calls": evidence["calls"],
            "model": provider.model,
        }
        results.append(result)
        print(json.dumps(result), flush=True)
    summary = {
        "evaluated": len(results),
        "passed": sum(r["passed"] for r in results),
        "failed": sum(not r["passed"] for r in results),
        "results": results,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("GEOMETRY_AGENT_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--repeats", type=int, default=1, choices=range(1, 4))
    parser.add_argument("--paid", action="store_true", required=True)
    parser.add_argument("--paraphrases", action="store_true")
    parser.add_argument(
        "--probes", action="store_true", help="Also evaluate initial creation and safe rejection"
    )
    args = parser.parse_args()
    from openai import OpenAI

    client = OpenAI()
    result = evaluate(
        args.fixtures,
        args.output,
        lambda: OpenAIProvider(client, args.model),
        args.repeats,
        paraphrases=args.paraphrases,
    )
    print(json.dumps(result))
    probes = (
        evaluate_probes(args.output / "probes", lambda: OpenAIProvider(client, args.model))
        if args.probes
        else {"failed": 0}
    )
    return 0 if result["failed"] == 0 and probes["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
