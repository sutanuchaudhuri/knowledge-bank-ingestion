"""Shared state handed to every suite."""
from __future__ import annotations

import os
import secrets
import uuid
from dataclasses import dataclass, field

from apitest.client import Api, Recorder


@dataclass
class Ctx:
    api: Api
    rec: Recorder
    mode: str                                   # "dev-readonly" | "test-writable"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    fixtures: dict = field(default_factory=dict)

    @property
    def writable(self) -> bool:
        return self.mode == "test-writable"

    @property
    def admin_key(self) -> str:
        return self.api.admin_key

    def unique_email(self, tag: str = "u") -> str:
        return f"apitest+{tag}.{self.run_id}.{secrets.token_hex(3)}@example.test"
