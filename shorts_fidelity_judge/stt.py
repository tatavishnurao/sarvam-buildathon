from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from .models import Segment, TargetTranscript


class SarvamSTTError(RuntimeError):
    pass


class SarvamSTTAdapter:
    endpoint = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, cache_dir: Path, timeout_seconds: float = 30, retries: int = 2) -> None:
        self.cache_dir, self.timeout_seconds, self.retries = cache_dir, timeout_seconds, retries

    def transcribe(self, audio_path: Path, target_language: str, model: str = "saaras:v3") -> TargetTranscript:
        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        cache_path = self.cache_dir / f"{digest}.json"
        if cache_path.exists():
            return self._to_transcript(json.loads(cache_path.read_text(encoding="utf-8")))
        key = os.getenv("SARVAM_API_KEY")
        if not key:
            raise SarvamSTTError("SARVAM_API_KEY is required when no manual target transcript is supplied")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with audio_path.open("rb") as audio:
                    response = requests.post(self.endpoint, headers={"api-subscription-key": key}, files={"file": (audio_path.name, audio)}, data={"model": model, "mode": "transcribe", "language_code": target_language}, timeout=self.timeout_seconds)
                response.raise_for_status()
                raw: dict[str, Any] = response.json()
                # Store the complete provider payload and non-secret request
                # metadata, so a later run never needs to re-send this audio.
                envelope = {"request": {"audio_sha256": digest, "audio_filename": audio_path.name,
                                        "target_language": target_language, "model": model,
                                        "endpoint": self.endpoint, "cached_at": datetime.now(UTC).isoformat()},
                            "response": raw}
                cache_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
                return self._to_transcript(envelope)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * (2**attempt))
        raise SarvamSTTError(f"Sarvam STT failed after {self.retries + 1} attempts: {last_error}")

    @staticmethod
    def _to_transcript(raw: dict[str, Any]) -> TargetTranscript:
        raw = raw.get("response", raw)
        entries = raw.get("diarized_transcript", {}).get("entries", [])
        segments = [Segment(id=f"target-{index + 1}", text=item["transcript"], start_seconds=item.get("start_time_seconds"), end_seconds=item.get("end_time_seconds"), speaker=item.get("speaker_id")) for index, item in enumerate(entries)]
        return TargetTranscript(transcript=raw.get("transcript", " ".join(item.text for item in segments)), segments=segments, provenance="sarvam_stt", raw_response=raw)
