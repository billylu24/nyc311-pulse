"""Typed contracts for the privacy-minimized NYC 311 extract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ServiceRequest(BaseModel):
    """Only fields required by the analysis; precise addresses are intentionally absent."""

    model_config = ConfigDict(extra="ignore")

    unique_key: str = Field(min_length=1)
    created_date: datetime
    closed_date: datetime | None = None
    agency: str = Field(min_length=1)
    agency_name: str | None = None
    complaint_type: str = Field(min_length=1)
    descriptor: str | None = None
    status: str = Field(min_length=1)
    borough: str = Field(min_length=1)
    community_board: str = Field(min_length=1)
    open_data_channel_type: str = Field(min_length=1)

    @field_validator("agency", "complaint_type", "status", "borough", "community_board")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @model_validator(mode="after")
    def closed_after_created(self) -> ServiceRequest:
        if self.closed_date is not None and self.closed_date < self.created_date:
            raise ValueError("closed_date cannot precede created_date")
        return self


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    source_dataset: str
    window_start: str
    window_end: str
    extracted_at: str
    request_count: int = Field(ge=1)
    artifact_sha256: str
