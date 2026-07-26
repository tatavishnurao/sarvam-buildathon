"""Truthful, backend-owned language and dubbing capability declarations."""
from __future__ import annotations

import os

from backend.models.api import CapabilityResponse


SUPPORTED_LOCALES = (
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "bn-IN", "mr-IN",
    "gu-IN", "ml-IN", "pa-IN", "od-IN", "as-IN",
)


def dubbing_provider_name() -> str:
    return os.getenv("DUBBING_PROVIDER", "manual_creator_studio")


def capabilities() -> CapabilityResponse:
    provider = dubbing_provider_name()
    # No official Sarvam Dubbing API contract is configured in this repository.
    # Keep these lists separate so a future verified provider can narrow them.
    return CapabilityResponse(
        source_stt_languages=list(SUPPORTED_LOCALES),
        translation_languages=list(SUPPORTED_LOCALES),
        tts_languages=list(SUPPORTED_LOCALES),
        enabled_dubbing_target_languages=list(SUPPORTED_LOCALES[1:]),
        automatic_dubbing_available=False,
        dubbing_provider=provider,
        dubbing_mode="manual_creator_studio",
    )
