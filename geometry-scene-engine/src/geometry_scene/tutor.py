from typing import Literal

from pydantic import Field

from .schemas import Identifier, Model, StateDelta


class GeometryAction(Model):
    action: Literal["GEOMETRY_STATE_DELTA"] = "GEOMETRY_STATE_DELTA"
    scene_id: Identifier
    current_math_step: str = Field(min_length=1, max_length=200)
    delta: StateDelta
    caption: str = Field(default="", max_length=2000)
