#!/usr/bin/env python3
"""Convenience wrapper — delegates to mathbank.ingestion.ingest_excel."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank.ingestion.ingest_excel import run_ingest
import argparse

p = argparse.ArgumentParser()
p.add_argument("--xlsx", required=True)
p.add_argument("--batch", required=True)
p.add_argument("--stage", default="all")
p.add_argument("--dry-run", action="store_true")

if __name__ == "__main__":
    run_ingest(p.parse_args())
