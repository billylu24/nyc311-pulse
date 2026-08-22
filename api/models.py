from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    label: str
    value: str
    note: str


class Signal(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    severity: Literal["high", "watch"]
    as_of: str
    district: str
    borough: str
    problem: str
    agency: str | None = None
    observed: float
    expected: float
    effect: float
    uncertainty: str
    persistence: int = Field(ge=1)
    trigger: str
    evidence: list[Evidence]
    data_quality_flags: list[str]
    limitation: str
    recommended_action: str
    title: str
    display_effect: str


class ErrorEnvelope(BaseModel):
    error: dict[str, Any]
