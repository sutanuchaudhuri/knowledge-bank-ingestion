"""
Multi-stage Excel → corpus ingestion pipeline.

Stages (run with --stage all or individually):
  discover   → detect all tabs in the spreadsheet
  validate   → normalise rows, flag errors
  build      → construct corpus entities
  markdown   → generate paper/question markdown
  upload     → mirror markdown to Google Drive
  sync       → upsert entity rows into Google Sheets
  embed      → chunk documents and upsert embeddings

See /requirements/03_INGESTION_PIPELINE_REQUIREMENTS.md for full spec.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import openpyxl
from rich.console import Console

console = Console()

STAGES = ["discover", "validate", "build", "markdown", "upload", "sync", "embed"]


def _data_dir(batch: str) -> Path:
    root = Path(__file__).resolve().parents[4] / "data" / "import"
    root.mkdir(parents=True, exist_ok=True)
    return root


def stage_discover(xlsx: Path, batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 1 — Discover tabs")
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    tabs = wb.sheetnames
    wb.close()
    out = _data_dir(batch) / "tabs.json"
    if not dry_run:
        out.write_text(json.dumps(tabs, indent=2))
    console.print(f"Found {len(tabs)} tabs: {tabs}")
    console.print(f"[green]Written → {out}" if not dry_run else "[yellow]dry-run: skipped write")


def stage_validate(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 2 — Validate + normalise rows")
    # TODO: implement row extraction and validation per IGR-002 / IGR-003
    console.print("[yellow]Stage not yet implemented — scaffold only")


def stage_build(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 3 — Build corpus entities")
    # TODO: implement entity construction per IGR-004
    console.print("[yellow]Stage not yet implemented — scaffold only")


def stage_markdown(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 4 — Generate markdown")
    # TODO: implement per MDR-001 / MDR-002
    console.print("[yellow]Stage not yet implemented — scaffold only")


def stage_upload(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 5 — Drive upload")
    # TODO: implement per IGR-006
    console.print("[yellow]Stage not yet implemented — scaffold only")


def stage_sync(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 6 — Sheets sync")
    # TODO: implement per IGR-007
    console.print("[yellow]Stage not yet implemented — scaffold only")


def stage_embed(batch: str, dry_run: bool) -> None:
    console.rule("[bold cyan]Stage 7 — Chunk + embed")
    # TODO: implement per IGR-008
    console.print("[yellow]Stage not yet implemented — scaffold only")


_STAGE_FNS = {
    "discover": lambda xlsx, batch, dry: stage_discover(xlsx, batch, dry),
    "validate": lambda _xlsx, batch, dry: stage_validate(batch, dry),
    "build":    lambda _xlsx, batch, dry: stage_build(batch, dry),
    "markdown": lambda _xlsx, batch, dry: stage_markdown(batch, dry),
    "upload":   lambda _xlsx, batch, dry: stage_upload(batch, dry),
    "sync":     lambda _xlsx, batch, dry: stage_sync(batch, dry),
    "embed":    lambda _xlsx, batch, dry: stage_embed(batch, dry),
}


def run_ingest(args: argparse.Namespace) -> None:
    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        console.print(f"[red]Excel file not found: {xlsx}")
        sys.exit(1)

    stages = STAGES if args.stage == "all" else [args.stage]
    for s in stages:
        _STAGE_FNS[s](xlsx, args.batch, args.dry_run)
