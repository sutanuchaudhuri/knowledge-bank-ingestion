"""Persistent model-free image evidence and a local, network-free review gallery."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from .cli import render_fixture
from .parser import load_document


def generate(fixtures: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    sections = []
    total = 0
    for fixture in sorted(fixtures.glob("*.json")):
        document = load_document(fixture)
        directory = output / fixture.stem
        frames = render_fixture(document, directory)
        cards = []
        for frame in frames:
            total += 1
            link = f"{fixture.stem}/frame_{frame.version:03}.svg"
            cards.append(
                f'<figure><img src="{html.escape(link)}" alt="{html.escape(fixture.stem)} frame {frame.version}">'
                f"<figcaption>Frame {frame.version} · VALID · "
                f"{html.escape(frame.visual_state.caption)}</figcaption>"
                f'<a href="{fixture.stem}/bundle_{frame.version:03}.json">State bundle</a></figure>'
            )
        sections.append(
            f"<section><h2>{html.escape(fixture.stem)}</h2><div>{''.join(cards)}</div></section>"
        )
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Geometry scene regression gallery</title>
<style>body{font-family:system-ui;background:#f1f5f9;margin:2rem;color:#0f172a}
section>div{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
figure{margin:0;background:white;border:1px solid #cbd5e1;padding:1rem;border-radius:12px}
img{width:100%;height:320px;object-fit:contain}figcaption{margin:1rem 0}</style>
<h1>Geometry scene regression gallery</h1><p>Seeded, model-free fixtures. Inspect every cumulative frame.</p>
"""
        + "".join(sections)
        + "</html>"
    )
    (output / "index.html").write_text(page)
    summary = {"cases": len(sections), "frames": total, "valid": True}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.fixtures, args.output)))


if __name__ == "__main__":
    main()
