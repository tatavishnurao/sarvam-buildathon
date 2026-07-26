from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


JobStatus = Literal[
    "created",
    "awaiting_source",
    "awaiting_dubbed_artifact",
    "queued",
    "extracting_audio",
    "transcribing_source",
    "transcribing_target",
    "back_translating",
    "comparing",
    "complete",
    "failed",
]


class CreateJobRequest(BaseModel):
    source_url: HttpUrl | None = None
    creator_authorised: bool
    target_language: str = "te-IN"
    source_language: str = "en-IN"
    expected_speakers: int | None = Field(default=2, ge=1, le=20)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str
    target_language: str
    source_language: str
    has_source: bool
    has_target: bool
    error: str | None = None


class CorrectionRequest(BaseModel):
    finding_id: str
    label: Literal[
        "true_issue", "acceptable_adaptation", "false_alarm", "cannot_judge"
    ]
    suggested_target_text: str | None = None
    approved: bool = False


class ArtifactResponse(BaseModel):
    job_id: str
    artifacts: dict[str, object]
