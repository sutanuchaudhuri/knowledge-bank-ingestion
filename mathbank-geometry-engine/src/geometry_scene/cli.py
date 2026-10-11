from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .errors import GeometryError, InvalidFrame
from .parser import load_document, parse_dsl
from .schemas import Frame, StateDelta
from .service import apply_delta, create_scene, validate_frame


def write_frame(frame: Frame, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    index = f"{frame.version:03}"
    for name in ("math_state", "scene_state", "visual_state", "validation"):
        (directory / f"{name}_{index}.json").write_text(
            getattr(frame, name).model_dump_json(indent=2) + "\n"
        )
    (directory / f"frame_{index}.svg").write_text(frame.svg)
    (directory / f"bundle_{index}.json").write_text(frame.model_dump_json(indent=2) + "\n")
    if frame.applied_delta:
        (directory / f"delta_{index}.json").write_text(
            frame.applied_delta.model_dump_json(indent=2) + "\n"
        )


def render_fixture(document, directory: Path):
    initial = document.get("initial", document)
    (directory).mkdir(parents=True, exist_ok=True)
    (directory / "input.json").write_text(json.dumps(document, indent=2) + "\n")
    frame = create_scene(parse_dsl(initial))
    frames = [frame]
    write_frame(frame, directory)
    for step in document.get("steps", []):
        delta = StateDelta.model_validate(step.get("delta", step))
        frame = apply_delta(frame, delta)
        frames.append(frame)
        write_frame(frame, directory)
    return frames


def main():
    parser = argparse.ArgumentParser(prog="geometry-scene")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render")
    render.add_argument("fixture", type=Path)
    render.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("scene", type=Path)
    apply.add_argument("delta", type=Path)
    apply.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "render":
            frames = render_fixture(load_document(args.fixture), args.output)
            print(json.dumps({"valid": True, "frames": len(frames), "output": str(args.output)}))
        elif args.command == "apply":
            frame = Frame.model_validate(load_document(args.scene))
            updated = apply_delta(frame, StateDelta.model_validate(load_document(args.delta)))
            write_frame(updated, args.output)
            print(json.dumps({"valid": True, "version": updated.version}))
        else:
            paths = sorted(args.directory.glob("bundle_*.json"))
            if not paths:
                raise GeometryError("no saved frame bundles found")
            for path in paths:
                frame = Frame.model_validate(load_document(path))
                svg_path = path.with_name(
                    path.name.replace("bundle_", "frame_").replace(".json", ".svg")
                )
                frame = frame.model_copy(update={"svg": svg_path.read_text()})
                report = validate_frame(frame)
                if not report.valid:
                    raise InvalidFrame("; ".join(report.errors), frame)
            print(json.dumps({"valid": True, "frames": len(paths)}))
    except (GeometryError, ValueError, OSError) as exc:
        if isinstance(exc, InvalidFrame) and hasattr(args, "output"):
            write_frame(exc.frame, args.output)
        if hasattr(args, "output"):
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "failure.json").write_text(
                json.dumps(
                    {
                        "valid": False,
                        "message": str(exc),
                        "diagnostics": exc.details if isinstance(exc, GeometryError) else {},
                        "input_path": str(getattr(args, "fixture", getattr(args, "scene", ""))),
                        "delta_path": str(getattr(args, "delta", "")),
                    },
                    indent=2,
                )
                + "\n"
            )
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
