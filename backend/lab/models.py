from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Step(StrictModel):
    setpoint: float = Field(ge=0, le=1)
    duration_ms: int = Field(ge=10, le=60_000, strict=True)


class Recipe(StrictModel):
    sample_rate_hz: Literal[10, 20, 25, 50, 100] = 50
    seed: int = Field(default=7, ge=1, le=2_147_483_647, strict=True)
    steps: list[Step] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_ticks(self) -> "Recipe":
        period = 1000 // self.sample_rate_hz
        if any(step.duration_ms % period for step in self.steps):
            raise ValueError("Each step must contain whole sample periods")
        if sum(step.duration_ms for step in self.steps) > 60_000:
            raise ValueError("A run must last at most sixty seconds")
        return self


class StartRequest(StrictModel):
    command_id: UUID
    name: str = Field(min_length=1, max_length=80)
    recipe: Recipe
    alpha: float = Field(default=0.15, gt=0, le=1)
    recipe_version_id: UUID | None = None
    scenario: Literal[
        "normal", "lost_start_ack", "telemetry_reconnect", "controller_disconnect", "database_write_failure"
    ] = "normal"


class StopRequest(StrictModel):
    command_id: UUID


class RecipeSaveRequest(StrictModel):
    request_id: UUID
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    recipe: Recipe
    alpha: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def nonblank_name(self) -> "RecipeSaveRequest":
        if not self.name.strip():
            raise ValueError("Give the recipe a name")
        return self


class Sample(StrictModel):
    seq: int = Field(ge=0, le=5999, strict=True)
    logical_s: float = Field(gt=0, le=60)
    setpoint: float = Field(ge=0, le=1)
    response: float
    reference: float
    source_utc: str
    device_elapsed_s: float = Field(ge=0)
