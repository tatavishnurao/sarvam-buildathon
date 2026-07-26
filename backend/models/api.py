from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


JobStatus = Literal[
    "created",
    "awaiting_source",
    "source_language_confirmation_required",
    "awaiting_dubbing",
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
    target_language: str
    source_language: str = "auto"
    expected_speakers: int | None = Field(default=None, ge=1, le=20)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    message: str
    target_language: str
    source_language: str
    detected_source_language: str | None = None
    source_language_confidence: float | None = None
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


class SourceLanguageConfirmationRequest(BaseModel):
    source_language: str


class CapabilityResponse(BaseModel):
    source_stt_languages: list[str]
    translation_languages: list[str]
    tts_languages: list[str]
    enabled_dubbing_target_languages: list[str]
    automatic_dubbing_available: bool
    dubbing_provider: str
    dubbing_mode: str
