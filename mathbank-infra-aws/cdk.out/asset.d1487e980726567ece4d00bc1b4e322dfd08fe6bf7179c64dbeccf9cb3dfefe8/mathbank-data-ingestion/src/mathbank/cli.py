"""CLI entry-point wired to pyproject.toml [project.scripts]."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mathbank",
        description="MathBank competition corpus pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest the master Excel spreadsheet")
    ingest_p.add_argument("--xlsx", required=True)
    ingest_p.add_argument("--batch", required=True)
    ingest_p.add_argument("--stage", default="all")
    ingest_p.add_argument("--dry-run", action="store_true")

    firestore_p = sub.add_parser("setup-firestore", help="Bootstrap Firestore collections")
    firestore_p.add_argument("--project", required=True)
    firestore_p.add_argument("--database", default="(default)")
    firestore_p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "ingest":
        from mathbank.ingestion.ingest_excel import run_ingest
        run_ingest(args)
    elif args.command == "setup-firestore":
        from mathbank.firestore.setup import run_setup
        run_setup(args)
    else:
        parser.print_help()
        sys.exit(1)
