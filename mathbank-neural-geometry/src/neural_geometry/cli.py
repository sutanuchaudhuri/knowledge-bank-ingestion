from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from pydantic import ValidationError

from .compiler import CompileError, compile_program
from .examples import examples
from .models import ConstructionProgram, TrustedFacts


def write_sequence(program: ConstructionProgram, facts: TrustedFacts, output: Path) -> dict:
    frames = compile_program(program, facts)
    output.mkdir(parents=True, exist_ok=True)
    (output / "program.json").write_text(program.model_dump_json(indent=2) + "\n")
    (output / "trusted_facts.json").write_text(facts.model_dump_json(indent=2) + "\n")
    for frame in frames:
        (output / f"frame_{frame.step:03d}.svg").write_text(frame.svg + "\n")
        (output / f"frame_{frame.step:03d}.json").write_text(frame.model_dump_json(indent=2) + "\n")
    report = {
        "program": program.id,
        "frames": len(frames),
        "valid": True,
        "program_hash": frames[-1].program_hash,
        "compiler_version": "0.1.0",
        "schema_version": program.schema_version,
        "validation": [frame.core.validation.model_dump(mode="json") for frame in frames],
        "layout_values": [value.model_dump(mode="json") for value in frames[-1].layout_values],
        "replacements": [value.model_dump(mode="json") for value in frames[-1].replacements],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def gallery(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    sections = []
    reports = []
    for name, (program, facts) in examples().items():
        report = write_sequence(program, facts, output / name)
        reports.append(report)
        images = "".join(
            f'<figure><img src="{name}/frame_{step:03d}.svg" '
            f'alt="{html.escape(program.id)} step {step}" loading="lazy">'
            f"<figcaption>Step {step}</figcaption></figure>"
            for step in range(report["frames"])
        )
        sections.append(f"<section><h2>{html.escape(program.id)}</h2>{images}</section>")
    document = (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Neural Geometry Compiler - independent examples</title>"
        "<style>body{font:16px system-ui;margin:24px;background:#f8fafc;color:#0f172a}"
        "section{display:flex;flex-wrap:wrap;gap:16px}h2{width:100%}"
        "figure{margin:0;flex:1 1 320px;max-width:640px;background:white;border:1px solid #cbd5e1}"
        "img{width:100%;display:block}figcaption{padding:8px}</style>"
        "<h1>Neural-Symbolic Geometry Compiler</h1>"
        "<p>Typed-program foundation, not trained-model acceptance. "
        "Provisional guides are dashed and are never mathematical facts.</p>"
        + "".join(sections)
        + "</html>"
    )
    (output / "index.html").write_text(document)
    summary = {
        "cases": len(reports),
        "frames": sum(report["frames"] for report in reports),
        "reports": reports,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent typed geometry compiler foundation")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("gallery")
    generate.add_argument("--output", type=Path, required=True)
    compile_command = sub.add_parser("compile")
    compile_command.add_argument("program", type=Path)
    compile_command.add_argument("--output", type=Path, required=True)
    compile_command.add_argument(
        "--trusted-facts",
        type=Path,
        help="Host-verified evidence file; never use unverified planner output here",
    )
    args = parser.parse_args()
    try:
        if args.command == "gallery":
            result = gallery(args.output)
        else:
            program = ConstructionProgram.model_validate_json(args.program.read_text())
            facts = (
                TrustedFacts.model_validate_json(args.trusted_facts.read_text())
                if args.trusted_facts
                else TrustedFacts()
            )
            result = write_sequence(program, facts, args.output)
    except (CompileError, ValidationError) as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "code": getattr(exc, "code", "INVALID_IR"),
                    "step": getattr(exc, "step", None),
                    "message": str(exc),
                }
            )
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
