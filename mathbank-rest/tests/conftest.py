"""Suite-wide offline guard: the learner JWT dependency reads `student_profile.status` (LRN-F11).

Tests that mint real tokens must never reach a database for that lookup, so every test sees an ACTIVE student unless
it monkeypatches `security._load_student_status` itself (see tests/test_wp1_identity.py).
"""
from __future__ import annotations

import pytest

from mathbank_rest import security


@pytest.fixture(autouse=True)
def _offline_student_status(monkeypatch):
    security._status_cache.clear()
    monkeypatch.setattr(security, "_load_student_status", lambda student_id: "ACTIVE")
    yield
    security._status_cache.clear()
