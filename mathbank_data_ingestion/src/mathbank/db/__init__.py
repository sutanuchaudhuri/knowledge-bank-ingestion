"""db package — SQLite local corpus store."""
from pathlib import Path

# Canonical DB path: mathbank/data/mathbank.db
DB_PATH = Path(__file__).resolve().parents[3] / "data" / "mathbank.db"
