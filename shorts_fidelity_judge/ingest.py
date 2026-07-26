from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from .stt import SarvamSTTAdapter


class CaseConfig(BaseModel):
    case_id: str
    source_url: HttpUrl | None = None
    creator: str
    creator_authorised: bool = False
    source_language: str = "en-IN"
    target_language: str
    expected_speakers: int | None = None
    source_video: Path
    dubbed_audio: Path
    metadata: dict[str, Any] = Field(default_factory=dict)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed ({exc.returncode}): {' '.join(command)}") from exc


def extract_audio(source_video: Path, output_wav: Path) -> None:
    if not source_video.is_file():
        raise FileNotFoundError(source_video)
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ]
    )


def _write_transcript(path: Path, transcript: Any) -> None:
    path.write_text(
        json.dumps(transcript.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ingest(case_path: Path) -> Path:
    case_path = case_path.resolve()
    case_dir = case_path.parent
    case = CaseConfig.model_validate_json(case_path.read_text(encoding="utf-8"))

    source_video = (case_dir / case.source_video).resolve()
    dubbed_audio = (case_dir / case.dubbed_audio).resolve()
    artifacts = case_dir / "artifacts"
    raw_cache = artifacts / "raw" / "sarvam-stt"
    artifacts.mkdir(parents=True, exist_ok=True)

    if not dubbed_audio.is_file():
        raise FileNotFoundError(
            f"Dubbed audio is missing: {dubbed_audio}. Export the target-language WAV "
            "from Sarvam Creator Studio and place it at the path declared in case.json."
        )

    source_audio = artifacts / "source_audio.wav"
    extract_audio(source_video, source_audio)

    stt = SarvamSTTAdapter(raw_cache)
    source_transcript = stt.transcribe(
        source_audio,
        case.source_language,
        with_diarization=True,
        num_speakers=case.expected_speakers,
    )
    target_transcript = stt.transcribe(
        dubbed_audio,
        case.target_language,
        with_diarization=True,
        num_speakers=case.expected_speakers,
    )

    _write_transcript(artifacts / "source_transcript.json", source_transcript)
    _write_transcript(artifacts / "target_transcript.json", target_transcript)

    copied_dub = artifacts / f"dubbed_{case.target_language}.wav"
    if dubbed_audio != copied_dub:
        shutil.copy2(dubbed_audio, copied_dub)

    manifest = {
        "case_id": case.case_id,
        "source_url": str(case.source_url) if case.source_url else None,
        "creator": case.creator,
        "creator_authorised": case.creator_authorised,
        "source_language": case.source_language,
        "target_language": case.target_language,
        "expected_speakers": case.expected_speakers,
        "created_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "source_video": str(source_video),
            "source_video_sha256": _sha256(source_video),
            "dubbed_audio": str(dubbed_audio),
            "dubbed_audio_sha256": _sha256(dubbed_audio),
        },
        "artifacts": {
            "source_audio": str(source_audio),
            "source_transcript": str(artifacts / "source_transcript.json"),
            "target_transcript": str(artifacts / "target_transcript.json"),
            "dubbed_audio_copy": str(copied_dub),
        },
        "models": {"speech_to_text": "saaras:v3", "transport": "batch"},
        "metadata": case.metadata,
    }
    manifest_path = artifacts / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create source and target transcript artifacts for one local Short"
    )
    parser.add_argument("case", type=Path, help="Path to tests/ytshorts/<case>/case.json")
    args = parser.parse_args()
    manifest_path = ingest(args.case)
    print(manifest_path)


if __name__ == "__main__":
    main()
