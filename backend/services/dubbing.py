"""Dubbing providers. Automatic generation is intentionally not guessed."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DubbingRequest:
    job_id: str
    source_video: Path
    source_language: str
    target_language: str


class DubbingProvider(Protocol):
    def create_dub(self, request: DubbingRequest) -> dict[str, str]: ...

    def get_status(self, job_id: str) -> dict[str, str]: ...

    def download_artifacts(self, job_id: str, destination: Path) -> None: ...


class ManualCreatorStudioProvider:
    """Truthful handoff: users export a dub from Creator Studio themselves."""

    name = "manual_creator_studio"

    def create_dub(self, request: DubbingRequest) -> dict[str, str]:
        return {
            "status": "awaiting_dubbing",
            "message": (
                "Source processed successfully. Automatic Sarvam Dubbing is not "
                "enabled for this account. Create the "
                f"{request.target_language} dub in Sarvam Creator Studio and upload its WAV or MP4 export."
            ),
        }

    def get_status(self, job_id: str) -> dict[str, str]:
        return {"status": "awaiting_dubbing", "job_id": job_id}

    def download_artifacts(self, job_id: str, destination: Path) -> None:
        raise RuntimeError("Manual Creator Studio exports must be uploaded by the reviewer")


class SarvamDubbingProvider:
    """Reserved for an official documented/event-provided implementation."""

    name = "sarvam_api"

    def __init__(self) -> None:
        raise RuntimeError(
            "DUBBING_PROVIDER=sarvam_api requires a verified official Sarvam Dubbing API implementation; none is configured."
        )


def get_dubbing_provider() -> DubbingProvider:
    from backend.services.capabilities import dubbing_provider_name

    provider = dubbing_provider_name()
    if provider == "manual_creator_studio":
        return ManualCreatorStudioProvider()
    if provider == "sarvam_api":
        return SarvamDubbingProvider()
    raise RuntimeError(f"Unsupported DUBBING_PROVIDER: {provider}")
