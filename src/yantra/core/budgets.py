"""Validated execution budget configuration; no enforcement is performed here."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionBudget(BaseModel):
    """Finite limits intended for a future runtime loop to enforce."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_model_calls: int = Field(default=8, ge=1)
    max_tool_calls: int = Field(default=16, ge=0)
    max_steps: int = Field(default=24, ge=1)
    max_wall_time_seconds: float = Field(default=300.0, gt=0, allow_inf_nan=False)
    max_tokens: int = Field(default=32_000, ge=1)
    max_cost_usd: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def model_calls_fit_step_limit(self) -> ExecutionBudget:
        if self.max_model_calls > self.max_steps:
            raise ValueError("max_model_calls cannot exceed max_steps")
        return self
