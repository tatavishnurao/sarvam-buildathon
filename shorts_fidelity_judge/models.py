from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class Status(StrEnum):
    PRESERVED = "preserved"
    REVIEW_REQUIRED = "review_required"
    UNABLE_TO_VERIFY = "unable_to_verify"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Manifest(BaseModel):
    video_id: str
    creator: str
    source_url: HttpUrl
    target_language: str
    source_transcript: Path
    dubbed_wav: Path | None = None
    target_transcript: Path | None = None
    stt: dict[str, Any] = Field(default_factory=dict)


class Segment(BaseModel):
    id: str
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    speaker: str | None = None


class TargetTranscript(BaseModel):
    transcript: str = ""
    back_translation: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    provenance: Literal["manual", "sarvam_stt"] = "manual"
    raw_response: dict[str, Any] | None = None


class Finding(BaseModel):
    category: str
    severity: Severity
    source_segment_id: str | None = None
    target_segment_id: str | None = None
    source_text: str
    target_text: str
    evidence: str
    uncertainty: str
    recommended_action: str
    deterministic: bool = True


class SemanticVerdict(BaseModel):
    status: Status
    findings: list[Finding] = Field(default_factory=list)
    rationale: str

