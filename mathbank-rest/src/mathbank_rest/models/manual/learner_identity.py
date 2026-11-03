"""Refinements of the identity items of ``mb-learner`` (requirement 71 WP5, requirement 70 C1 sections 1, 3 and 4).

The generated ``LearnerProfile`` describes the migrated data exactly. This module registers a stricter subclass under the same
``(ctx, item_type)`` (the later registration replaces the generated one) and adds what the design needs but the migration never
wrote: ``phone`` (the migration copies it, but every migrated value was null), ``disabled_at`` (T4) and the ``RATE#pw`` counter
(T6). Every constraint below holds for each migrated item (statuses are normalised by the migration to ACTIVE/DISABLED/ERASING;
``DELETED`` stays accepted for rows written by the PostgreSQL account lifecycle).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, UtcDateTime
from mathbank_rest.models.ddb import learner as generated

ProfileStatus = Literal["ACTIVE", "DISABLED", "DELETED", "ERASING"]
COGNITO_PASSWORD = "!COGNITO"
_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class LearnerProfile(generated.LearnerProfile, ctx="learner", item_type="PROFILE"):
    status: ProfileStatus
    email: StrictStr = Field(min_length=3, max_length=320)
    email_lc: StrictStr = Field(min_length=3, max_length=320)
    first_name: StrictStr = Field(max_length=200)
    last_name: StrictStr = Field(max_length=200)
    display_name: StrictStr = Field(max_length=400)
    token_version: StrictInt = Field(ge=0)
    grade: StrictStr | None = Field(default=None, max_length=50)
    phone: StrictStr | None = Field(default=None, max_length=30)
    disabled_at: UtcDateTime | None = None


IdentityProfile = LearnerProfile


class LearnerRatePw(DdbItem, ctx="learner", item_type="RATE_PW"):
    """Fixed-window counter of password-change attempts (T6: 5 per 15 minutes per student); expires through ``ttl``."""

    type: Literal["RATE_PW"] = "RATE_PW"
    PK: str = Field(pattern=f"^STUDENT#{_UUID}$")
    SK: str = Field(pattern="^RATE#pw$")
    count: StrictInt = Field(ge=0)
    window_start: StrictInt = Field(ge=0)       # epoch seconds
