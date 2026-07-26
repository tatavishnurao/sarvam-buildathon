from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sarvamai import SarvamAI

from .config import load_repository_env
from .models import Segment, TargetTranscript

LOG = logging.getLogger(__name__)


class SarvamSTTError(RuntimeError):
    pass


class SarvamSTTAdapter:
    """Cached Saaras v3 Batch STT adapter.

    Shorts frequently exceed the synchronous REST API's 30-second limit. The
    Batch API supports files up to two hours and is the only documented STT
    transport that returns diarisation plus chunk timestamps, so it is the
    default for both source English audio and the dubbed target-language WAV.
    """

    def __init__(self, cache_dir: Path, *, env_path: Path | None = None) -> None:
        self.cache_dir = cache_dir
        self.env_path = env_path

    def transcribe(
        self,
        audio_path: Path,
        language_code: str,
        model: str = "saaras:v3",
        *,
        with_diarization: bool = True,
        num_speakers: int | None = None,
        mode: str = "transcribe",
    ) -> TargetTranscript:
        if not audio_path.is_file():
            raise SarvamSTTError(f"Audio file does not exist: {audio_path}")

        digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "audio_sha256": digest,
                    "language_code": language_code,
                    "model": model,
                    "mode": mode,
                    "with_diarization": with_diarization,
                    "num_speakers": num_speakers,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"
        pending_path = self.cache_dir / f"{cache_key}.pending.json"
        if cache_path.exists():
            transcript = self._to_transcript(
                json.loads(cache_path.read_text(encoding="utf-8"))
            )
            if not transcript.transcript.strip():
                raise SarvamSTTError(
                    f"Cached Sarvam STT response is invalid: {cache_path.name}"
                )
            LOG.info("Using cached Sarvam STT response %s", cache_path.name)
            return transcript

        load_repository_env(self.env_path)
        key = os.getenv("SARVAM_API_KEY")
        if not key:
            raise SarvamSTTError("SARVAM_API_KEY is required when no cached transcript exists")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        download_dir = self.cache_dir / f"{cache_key}.download"
        if download_dir.exists():
            shutil.rmtree(download_dir)
        download_dir.mkdir(parents=True)

        try:
            client = SarvamAI(api_subscription_key=key)
            kwargs: dict[str, Any] = {
                "model": model,
                "mode": mode,
                "language_code": language_code,
                "with_diarization": with_diarization,
            }
            if num_speakers is not None:
                kwargs["num_speakers"] = num_speakers

            if pending_path.is_file():
                pending = json.loads(pending_path.read_text(encoding="utf-8"))
                job = client.speech_to_text_job.get_job(pending["provider_job_id"])
                LOG.info("Resuming Sarvam Batch STT job %s", job.job_id)
            else:
                job = client.speech_to_text_job.create_job(**kwargs)
                pending_path.write_text(
                    json.dumps(
                        {
                            "provider_job_id": job.job_id,
                            "audio_sha256": digest,
                            "language_code": language_code,
                            "model": model,
                            "mode": mode,
                            "with_diarization": with_diarization,
                            "num_speakers": num_speakers,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                LOG.info("Created Sarvam Batch STT job %s", job.job_id)
                job.upload_files(file_paths=[str(audio_path)])
                LOG.info(
                    "Uploaded %s for Sarvam Batch STT job %s",
                    audio_path.name,
                    job.job_id,
                )
                job.start()
            final_status = self._wait_for_job(job)

            file_results = job.get_file_results()
            failed = file_results.get("failed", [])
            if failed:
                raise SarvamSTTError(f"Sarvam batch STT file failed: {failed}")

            self._download_with_retry(job, download_dir)
            json_outputs = sorted(download_dir.rglob("*.json"))
            if not json_outputs:
                raise SarvamSTTError("Sarvam batch STT completed but returned no JSON output")

            raw = json.loads(json_outputs[0].read_text(encoding="utf-8"))
            envelope = {
                "request": {
                    "audio_sha256": digest,
                    "audio_filename": audio_path.name,
                    "language_code": language_code,
                    "model": model,
                    "mode": mode,
                    "with_diarization": with_diarization,
                    "num_speakers": num_speakers,
                    "cached_at": datetime.now(UTC).isoformat(),
                    "provider_job_id": job.job_id,
                    "terminal_job_state": final_status.job_state,
                },
                "response": raw,
                "file_results": file_results,
            }
            cache_path.write_text(
                json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            pending_path.unlink(missing_ok=True)
            return self._to_transcript(envelope)
        except SarvamSTTError:
            raise
        except Exception as exc:  # SDK exceptions are not stable across versions.
            message = str(exc)
            if key:
                message = message.replace(key, "[REDACTED]")
            raise SarvamSTTError(
                f"Sarvam batch STT failed ({type(exc).__name__}): {message[:500]}"
            ) from exc
        finally:
            shutil.rmtree(download_dir, ignore_errors=True)

    @staticmethod
    def _wait_for_job(job: Any, timeout_seconds: int = 600) -> Any:
        started = time.monotonic()
        delay = 3
        while True:
            status = job.get_status()
            state = str(status.job_state)
            LOG.info("Sarvam Batch STT job %s state=%s", job.job_id, state)
            normalized = state.casefold()
            if normalized == "completed":
                return status
            if normalized == "failed":
                raise SarvamSTTError(
                    f"Sarvam Batch STT job {job.job_id} reached terminal state Failed"
                )
            if time.monotonic() - started >= timeout_seconds:
                raise SarvamSTTError(
                    f"Sarvam Batch STT job {job.job_id} timed out after {timeout_seconds} seconds"
                )
            time.sleep(delay)
            delay = min(delay * 2, 30)

    @staticmethod
    def _download_with_retry(
        job: Any, download_dir: Path, attempts: int = 3
    ) -> None:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                job.download_outputs(output_dir=str(download_dir))
                return
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    delay = 2**attempt
                    LOG.warning(
                        "Sarvam job %s result download failed; retrying in %ss",
                        job.job_id,
                        delay,
                    )
                    time.sleep(delay)
        raise SarvamSTTError(
            f"Sarvam Batch STT result download failed after {attempts} attempts "
            f"for job {job.job_id}: {type(last_error).__name__}"
        ) from last_error

    @staticmethod
    def _to_transcript(raw: dict[str, Any]) -> TargetTranscript:
        payload = raw.get("response", raw)
        entries = (payload.get("diarized_transcript") or {}).get("entries", [])
        segments = [
            Segment(
                id=f"target-{index + 1}",
                text=item.get("transcript", "").strip(),
                start_seconds=item.get("start_time_seconds"),
                end_seconds=item.get("end_time_seconds"),
                speaker=item.get("speaker_id"),
            )
            for index, item in enumerate(entries)
            if item.get("transcript", "").strip()
        ]
        transcript = payload.get("transcript") or " ".join(item.text for item in segments)
        return TargetTranscript(
            transcript=transcript,
            segments=segments,
            provenance="sarvam_stt",
            raw_response=payload,
        )
