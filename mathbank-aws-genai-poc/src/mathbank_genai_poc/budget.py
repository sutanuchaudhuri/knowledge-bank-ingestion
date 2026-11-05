"""Cumulative paid-audio guardrail for the POC (a local ledger, not an AWS billing control).

Nova Sonic bills streamed input and generated output audio, and the browser streams microphone audio for the whole time
a session is connected. Wall-clock connected time is therefore the conservative measure recorded here.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path


class BudgetExhausted(RuntimeError):
    pass


class AudioBudget:
    def __init__(self, ledger: Path, limit_seconds: float):
        self.ledger = ledger
        self.limit = float(limit_seconds)
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            data = json.loads(self.ledger.read_text())
            return {"used_seconds": float(data.get("used_seconds", 0.0)), "sessions": list(data.get("sessions", []))}
        except FileNotFoundError:
            return {"used_seconds": 0.0, "sessions": []}

    def _write(self, data: dict) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.ledger.parent, prefix=".usage-")
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, self.ledger)

    def used(self) -> float:
        with self._lock:
            return self._read()["used_seconds"]

    def remaining(self) -> float:
        return max(0.0, self.limit - self.used())

    def grant(self, requested: float) -> float:
        """Seconds the next session may run; raises when less than 10 seconds of budget remain."""
        available = self.remaining()
        if available < 10:
            raise BudgetExhausted(f"POC audio budget exhausted ({self.limit:.0f}s used or reserved)")
        return min(float(requested), available)

    def record(self, seconds: float, reason: str) -> float:
        with self._lock:
            data = self._read()
            data["used_seconds"] = round(data["used_seconds"] + max(0.0, seconds), 2)
            data["sessions"].append({"ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                     "seconds": round(seconds, 2), "reason": reason})
            self._write(data)
            return data["used_seconds"]
