#!/usr/bin/env python3
"""Convenience wrapper — delegates to mathbank.firestore.setup."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank.firestore.setup import run_setup
import argparse

p = argparse.ArgumentParser()
p.add_argument("--project", required=True)
p.add_argument("--database", default="(default)")
p.add_argument("--dry-run", action="store_true")

if __name__ == "__main__":
    run_setup(p.parse_args())
