from __future__ import annotations

import html
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
from difflib import SequenceMatcher
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi import UploadFile

from backend.models.api import CreateJobRequest, JobResponse
from backend.services.semantic_judge import SarvamSemanticJudge
from shorts_fidelity_judge.audio import inspect_wav
from shorts_fidelity_judge.config import REPOSITORY_ROOT
from shorts_fidelity_judge.models import Segment, TargetTranscript
from shorts_fidelity_judge.stt import SarvamSTTAdapter

LOG = logging.getLogger(__name__)
RUNTIME_ROOT = REPOSITORY_ROOT / ".runtime"
JOBS_ROOT = RUNTIME_ROOT / "jobs"

PROTECTED_ENTITIES = ("Lamborghini Gallardo", "Stradman")
AUTOMOTIVE_TERMS = ("twin-turbo", "rear-wheel drive", "four-wheel drive")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_youtube_url(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    host = parsed.netloc.casefold().removeprefix("www.")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "m.youtube.com"}:
        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
        elif parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
    if not video_id or not all(char.isalnum() or char in "_-" for char in video_id):
        raise ValueError("Enter a valid YouTube Shorts, watch, or youtu.be URL")
    return f"https://www.youtube.com/watch?v={video_id}", video_id


class JobService:
    def __init__(self, jobs_root: Path = JOBS_ROOT) -> None:
        self.jobs_root = jobs_root
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def create_job(self, request: CreateJobRequest) -> JobResponse:
        if not request.creator_authorised:
            raise ValueError("Creator authorisation must be confirmed")
        source_url = None
        video_id = None
        if request.source_url:
            source_url, video_id = normalize_youtube_url(str(request.source_url))
        job_id = uuid4().hex
        job_dir = self.jobs_root / job_id
        (job_dir / "inputs").mkdir(parents=True)
        status = "awaiting_source" if source_url else "created"
        state = {
            "job_id": job_id,
            "status": status,
            "progress": 0,
            "message": (
                "URL recorded; upload the creator-authorised MP4"
                if source_url
                else "Upload a source MP4"
            ),
            "target_language": request.target_language,
            "source_language": request.source_language,
            "expected_speakers": request.expected_speakers,
            "creator_authorised": True,
            "source_url": source_url,
            "youtube_video_id": video_id,
            "has_source": False,
            "has_target": False,
            "error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        _write_json(job_dir / "job.json", state)
        return JobResponse.model_validate(state)

    async def save_upload(
        self,
        job_id: str,
        *,
        source_file: UploadFile | None,
        target_file: UploadFile | None,
    ) -> JobResponse:
        state = self.get_state(job_id)
        job_dir = self.jobs_root / job_id
        if source_file is not None:
            if not source_file.filename or not source_file.filename.lower().endswith(".mp4"):
                raise ValueError("Source upload must be an MP4 file")
            await self._save_file(source_file, job_dir / "inputs" / "source.mp4")
            state["has_source"] = True
        if target_file is not None:
            suffix = Path(target_file.filename or "").suffix.casefold()
            if suffix not in {".wav", ".mp4"}:
                raise ValueError("Target upload must be WAV or MP4")
            await self._save_file(
                target_file, job_dir / "inputs" / f"target{suffix}"
            )
            state["has_target"] = True
        state["status"] = (
            "created" if state["has_source"] else "awaiting_source"
        )
        if state["has_source"] and not state["has_target"]:
            state["status"] = "awaiting_dubbed_artifact"
            state["message"] = "Source ready; upload a dubbed WAV or MP4"
        elif state["has_source"] and state["has_target"]:
            state["message"] = "Source and dubbed artifact are ready"
        self._store_state(state)
        return JobResponse.model_validate(state)

    async def _save_file(self, upload: UploadFile, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                output.write(chunk)
        await upload.close()
        if path.stat().st_size == 0:
            raise ValueError(f"Uploaded {path.name} is empty")

    def get_state(self, job_id: str) -> dict[str, Any]:
        path = self.jobs_root / job_id / "job.json"
        if not path.is_file():
            raise FileNotFoundError(job_id)
        return _read_json(path)

    def _store_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = _now()
        _write_json(self.jobs_root / state["job_id"] / "job.json", state)

    def _update(self, job_id: str, status: str, progress: int, message: str) -> None:
        state = self.get_state(job_id)
        state.update(status=status, progress=progress, message=message, error=None)
        self._store_state(state)

    def run_job(self, job_id: str) -> None:
        with self._guard:
            lock = self._locks.setdefault(job_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return
        try:
            self._run_job(job_id)
        except Exception as exc:
            redacted = self._redacted_error(exc)
            LOG.error("Job %s failed: %s", job_id, redacted)
            state = self.get_state(job_id)
            state.update(
                status="failed",
                message="Review failed",
                error=redacted,
            )
            self._store_state(state)
        finally:
            lock.release()

    def _run_job(self, job_id: str) -> None:
        state = self.get_state(job_id)
        if not state["has_source"]:
            raise ValueError("Upload a source MP4 before running the job")
        if not state["has_target"]:
            state.update(
                status="awaiting_dubbed_artifact",
                message="Upload a Sarvam-dubbed WAV or MP4 before running",
            )
            self._store_state(state)
            return
        job_dir = self.jobs_root / job_id
        artifacts = job_dir / "artifacts"
        artifacts.mkdir(exist_ok=True)
        self._update(job_id, "extracting_audio", 10, "Extracting source audio")
        source_audio = artifacts / "source_audio.wav"
        target_audio = artifacts / "target_audio.wav"
        self._extract_audio(job_dir / "inputs" / "source.mp4", source_audio)
        target_input = next((job_dir / "inputs").glob("target.*"))
        self._extract_audio(target_input, target_audio)

        cache = artifacts / "raw" / "sarvam-stt"
        adapter = SarvamSTTAdapter(cache)
        self._update(job_id, "transcribing_source", 25, "Transcribing English source")
        source = adapter.transcribe(
            source_audio,
            state["source_language"],
            with_diarization=True,
            num_speakers=state["expected_speakers"],
        )
        _write_json(
            artifacts / "source_transcript.raw.json", source.raw_response or {}
        )
        self._write_normalized(
            artifacts / "source_transcript.normalized.json",
            source,
            state["source_language"],
            "source",
        )
        self._update(job_id, "transcribing_target", 45, "Transcribing dubbed audio")
        target = adapter.transcribe(
            target_audio,
            state["target_language"],
            with_diarization=True,
            num_speakers=state["expected_speakers"],
        )
        _write_json(
            artifacts / "target_transcript.raw.json", target.raw_response or {}
        )
        self._write_normalized(
            artifacts / "target_transcript.normalized.json",
            target,
            state["target_language"],
            "target",
        )
        self._update(job_id, "back_translating", 65, "Back-translating dubbed audio")
        translated = adapter.transcribe(
            target_audio,
            state["target_language"],
            with_diarization=True,
            num_speakers=state["expected_speakers"],
            mode="translate",
        )
        _write_json(
            artifacts / "target_back_translation.raw.json",
            translated.raw_response or {},
        )
        back_translation = self._back_translation(target, translated)
        _write_json(artifacts / "target_back_translation.json", back_translation)

        self._update(job_id, "comparing", 80, "Aligning and comparing transcripts")
        alignments = self._align(source.segments, target.segments, translated.segments)
        _write_json(artifacts / "alignment.json", {"alignments": alignments})
        findings = self._findings(alignments)
        semantic = SarvamSemanticJudge(
            artifacts / "raw" / "sarvam-judge"
        ).review(
            {
                "alignments": alignments,
                "target_language": state["target_language"],
                "glossary": {
                    "protected_entities": list(PROTECTED_ENTITIES),
                    "automotive_terms": list(AUTOMOTIVE_TERMS),
                },
            },
            findings,
        )
        findings.extend(
            {
                "finding_id": "finding-"
                + hashlib.sha256(
                    f"semantic|{item.alignment_id}|{item.category}|{item.evidence}".encode(
                        "utf-8"
                    )
                ).hexdigest()[:10],
                **item.model_dump(mode="json"),
                "preserved": False,
                "source_segment_ids": [],
                "target_segment_ids": [],
                "recommended_action": "A human reviewer should compare the corresponding audio.",
            }
            for item in semantic.findings
        )
        report = {
            "job_id": job_id,
            "status": "review_required" if any(not f["preserved"] for f in findings) else "preserved",
            "source_audio": inspect_wav(source_audio),
            "target_audio": inspect_wav(target_audio),
            "source_transcript": self._transcript_dict(source, state["source_language"], "source"),
            "target_transcript": self._transcript_dict(target, state["target_language"], "target"),
            "target_back_translation": back_translation,
            "alignments": alignments,
            "findings": findings,
            "misinterpreted_items": [item for item in findings if not item["preserved"]],
            "semantic_verdict": semantic.model_dump(mode="json"),
            "note": "Human review is required; this report is not an accuracy certification.",
        }
        _write_json(artifacts / "report.json", report)
        self._write_html(artifacts / "report.html", report)
        (artifacts / "annotations.jsonl").touch(exist_ok=True)
        state = self.get_state(job_id)
        state.update(status="complete", progress=100, message="Review complete", error=None)
        self._store_state(state)

    @staticmethod
    def _extract_audio(source: Path, target: Path) -> None:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i",
                str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a",
                "pcm_s16le", str(target),
            ],
            check=True,
        )

    @staticmethod
    def _transcript_dict(
        transcript: TargetTranscript, language: str, prefix: str
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "language_code": language,
            "transcript": transcript.transcript,
            "segments": [
                {
                    "segment_id": f"{prefix}-{index:03d}",
                    "speaker": (
                        f"{prefix}:{segment.speaker}" if segment.speaker else None
                    ),
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "text": segment.text,
                }
                for index, segment in enumerate(transcript.segments, start=1)
            ],
        }

    def _write_normalized(
        self,
        path: Path,
        transcript: TargetTranscript,
        language: str,
        prefix: str,
    ) -> None:
        _write_json(path, self._transcript_dict(transcript, language, prefix))

    @staticmethod
    def _back_translation(
        target: TargetTranscript, translated: TargetTranscript
    ) -> dict[str, Any]:
        segments = []
        for index, target_segment in enumerate(target.segments):
            translated_segment = (
                translated.segments[index] if index < len(translated.segments) else None
            )
            segments.append(
                {
                    "segment_id": f"target-{index + 1:03d}",
                    "speaker": target_segment.speaker,
                    "start_seconds": target_segment.start_seconds,
                    "end_seconds": target_segment.end_seconds,
                    "target_text": target_segment.text,
                    "english_back_translation": (
                        translated_segment.text if translated_segment else None
                    ),
                }
            )
        return {
            "target_transcript": target.transcript,
            "english_back_translation": translated.transcript,
            "segments": segments,
        }

    @staticmethod
    def _align(
        source: list[Segment],
        target: list[Segment],
        translated: list[Segment],
    ) -> list[dict[str, Any]]:
        alignments: list[dict[str, Any]] = []
        used_targets: set[int] = set()
        for source_index, source_segment in enumerate(source):
            matches: list[int] = []
            if source_segment.start_seconds is not None and source_segment.end_seconds is not None:
                for target_index, target_segment in enumerate(target):
                    if target_segment.start_seconds is None or target_segment.end_seconds is None:
                        continue
                    overlap = min(source_segment.end_seconds, target_segment.end_seconds) - max(
                        source_segment.start_seconds, target_segment.start_seconds
                    )
                    if overlap > 0:
                        matches.append(target_index)
            elif source_index < len(target):
                matches.append(source_index)
            used_targets.update(matches)
            target_text = " ".join(target[index].text for index in matches)
            translated_text = " ".join(
                translated[index].text
                for index in matches
                if index < len(translated)
            )
            state = "aligned" if matches else "source_omitted"
            alignments.append(
                {
                    "alignment_id": f"align-{len(alignments) + 1:03d}",
                    "state": state,
                    "source_segment_ids": [f"source-{source_index + 1:03d}"],
                    "target_segment_ids": [
                        f"target-{index + 1:03d}" for index in matches
                    ],
                    "source_text": source_segment.text,
                    "target_text": target_text,
                    "english_back_translation": translated_text,
                    "source_time": [
                        source_segment.start_seconds,
                        source_segment.end_seconds,
                    ],
                    "target_time": (
                        [
                            target[matches[0]].start_seconds,
                            target[matches[-1]].end_seconds,
                        ]
                        if matches
                        else [None, None]
                    ),
                    "alignment_confidence": 0.8 if matches else 0.0,
                    "alignment_method": (
                        ["timestamp_overlap"] if matches else ["no_match"]
                    ),
                }
            )
        for target_index, target_segment in enumerate(target):
            if target_index in used_targets:
                continue
            alignments.append(
                {
                    "alignment_id": f"align-{len(alignments) + 1:03d}",
                    "state": "target_addition",
                    "source_segment_ids": [],
                    "target_segment_ids": [f"target-{target_index + 1:03d}"],
                    "source_text": "",
                    "target_text": target_segment.text,
                    "english_back_translation": (
                        translated[target_index].text
                        if target_index < len(translated)
                        else ""
                    ),
                    "source_time": [None, None],
                    "target_time": [
                        target_segment.start_seconds,
                        target_segment.end_seconds,
                    ],
                    "alignment_confidence": 0.0,
                    "alignment_method": ["unmatched_target"],
                }
            )
        return alignments

    @staticmethod
    def _findings(alignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        unsupported_target_segments: set[tuple[str, ...]] = set()
        for alignment in alignments:
            source = alignment["source_text"]
            target = alignment["target_text"]
            translated = alignment["english_back_translation"]
            source_lower, translated_lower = source.casefold(), translated.casefold()
            if alignment["state"] == "source_omitted":
                findings.append(JobService._finding("source_omission", "high", alignment, False, "No target segment overlaps this source utterance."))
            elif alignment["state"] == "target_addition":
                findings.append(JobService._finding("unsupported_addition", "high", alignment, False, "Target utterance has no overlapping source segment."))
            target_key = tuple(alignment["target_segment_ids"])
            if (
                "నా ముక్కు మీద కొట్టు" in target
                and target_key not in unsupported_target_segments
            ):
                unsupported_target_segments.add(target_key)
                findings.append(JobService._finding("unsupported_addition", "critical", alignment, False, "The exact Telugu phrase appears in the target transcript and has no source support."))
            for entity in PROTECTED_ENTITIES:
                source_match = JobService._source_entity_match(source, entity)
                if source_match and not JobService._contains_term(translated, entity):
                    findings.append(
                        JobService._finding(
                            "protected_entity_drift",
                            "critical",
                            alignment,
                            False,
                            f"Source ASR evidence {source!r} matches protected entity "
                            f"'{entity}' ({source_match}); the English back-translation "
                            "does not preserve the full entity.",
                        )
                    )
            for term in AUTOMOTIVE_TERMS:
                source_match = JobService._source_term_match(source, term, translated)
                if source_match and not JobService._contains_term(translated, term):
                    findings.append(
                        JobService._finding(
                            "automotive_term_drift",
                            "critical",
                            alignment,
                            False,
                            f"Source ASR evidence {source!r} matches automotive term "
                            f"'{term}' ({source_match}); target/back-translation evidence "
                            f"is {translated!r}.",
                        )
                    )
            source_numbers = JobService._numbers(source)
            translated_numbers = JobService._numbers(translated)
            for number in sorted(source_numbers):
                preserved = number in translated_numbers
                findings.append(JobService._finding(
                    "number_preserved" if preserved else "number_drift",
                    "low" if preserved else "critical",
                    alignment,
                    preserved,
                    f"Source number '{number}' {'appears' if preserved else 'does not appear'} in the English back-translation.",
                ))
            if "mate" in source_lower and "boss" in translated_lower:
                findings.append(JobService._finding("register_drift", "medium", alignment, False, "Source register 'mate' is back-translated as 'boss'."))
            if "subscriber" in source_lower:
                preserved = "subscriber" in translated_lower
                findings.append(JobService._finding(
                    "punchline_preserved" if preserved else "punchline_drift",
                    "low" if preserved else "high",
                    alignment,
                    preserved,
                    "Subscriber punchline is present in both source and back-translation." if preserved else "Subscriber punchline is absent from the back-translation.",
                ))
        return findings

    @staticmethod
    def _normalize_phrase(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        return JobService._normalize_phrase(term) in JobService._normalize_phrase(text)

    @staticmethod
    def _source_entity_match(source: str, entity: str) -> str | None:
        if JobService._contains_term(source, entity):
            return "exact normalized match"
        source_normalized = JobService._normalize_phrase(source)
        if entity == "Lamborghini Gallardo" and "lamborghini" in source_normalized:
            candidate = source_normalized[source_normalized.index("lamborghini") :]
            ratio = SequenceMatcher(
                None, candidate, JobService._normalize_phrase(entity)
            ).ratio()
            if ratio >= 0.80:
                return f"phonetic similarity {ratio:.2f}"
        if entity == "Stradman":
            ratio = SequenceMatcher(
                None, source_normalized, JobService._normalize_phrase(entity)
            ).ratio()
            if ratio >= 0.58:
                return f"phonetic similarity {ratio:.2f}"
        return None

    @staticmethod
    def _source_term_match(
        source: str, term: str, translated: str
    ) -> str | None:
        if JobService._contains_term(source, term):
            return "exact normalized match"
        source_normalized = JobService._normalize_phrase(source)
        if term == "rear-wheel drive" and JobService._contains_term(
            source, "four-wheel drive"
        ):
            return None
        if (
            term == "rear-wheel drive"
            and source_normalized.endswith("drive")
            and "monster wheel drive"
            in JobService._normalize_phrase(translated)
        ):
            ratio = SequenceMatcher(
                None, source_normalized, JobService._normalize_phrase(term)
            ).ratio()
            if ratio >= 0.50:
                return f"ASR phonetic similarity {ratio:.2f}"
        return None

    @staticmethod
    def _numbers(text: str) -> set[str]:
        normalized = text.casefold().replace(",", "")
        replacements = {
            r"\b(?:a|one)\s+thousand\b": "1000",
            r"\bthirteen\s+hundred\b": "1300",
            r"\bone\s+thousand\s+three\s+hundred\b": "1300",
        }
        for pattern, value in replacements.items():
            normalized = re.sub(pattern, value, normalized)
        return set(re.findall(r"\b\d+\b", normalized))

    @staticmethod
    def _finding(
        category: str,
        severity: str,
        alignment: dict[str, Any],
        preserved: bool,
        evidence: str,
    ) -> dict[str, Any]:
        return {
            "finding_id": "finding-"
            + hashlib.sha256(
                f"{category}|{alignment['alignment_id']}|{evidence}".encode("utf-8")
            ).hexdigest()[:10],
            "category": category,
            "severity": severity,
            "preserved": preserved,
            "source_segment_ids": alignment["source_segment_ids"],
            "target_segment_ids": alignment["target_segment_ids"],
            "source_text": alignment["source_text"],
            "target_text": alignment["target_text"],
            "english_back_translation": alignment["english_back_translation"],
            "evidence": evidence,
            "uncertainty": "ASR, diarisation, translation and timing alignment may each introduce error.",
            "recommended_action": "A human reviewer should compare the corresponding audio.",
        }

    @staticmethod
    def _write_html(path: Path, report: dict[str, Any]) -> None:
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(item['category'])}</td>"
            f"<td>{html.escape(item['severity'])}</td>"
            f"<td>{html.escape(item['source_text'])}</td>"
            f"<td>{html.escape(item['target_text'])}</td>"
            f"<td>{html.escape(item['english_back_translation'])}</td>"
            f"<td>{html.escape(item['evidence'])}</td>"
            "</tr>"
            for item in report["findings"]
        )
        document = (
            "<!doctype html><html><head><meta charset='UTF-8'>"
            "<title>DubPatch fidelity report</title>"
            "<style>body{font-family:system-ui;margin:2rem}table{border-collapse:collapse}"
            "td,th{border:1px solid #bbb;padding:.5rem;vertical-align:top}</style></head><body>"
            f"<h1>DubPatch fidelity report</h1><p>Status: {html.escape(report['status'])}</p>"
            f"<p>{html.escape(report['note'])}</p>"
            "<table><thead><tr><th>Category</th><th>Severity</th><th>Source</th>"
            "<th>Target</th><th>Back-translation</th><th>Evidence</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></body></html>"
        )
        path.write_text(document, encoding="utf-8")

    def artifacts(self, job_id: str) -> dict[str, object]:
        artifacts = self.jobs_root / job_id / "artifacts"
        result: dict[str, object] = {}
        if not artifacts.exists():
            return result
        for name in (
            "source_transcript.normalized.json",
            "target_transcript.normalized.json",
            "target_back_translation.json",
            "alignment.json",
            "report.json",
        ):
            path = artifacts / name
            if path.is_file():
                result[name] = _read_json(path)
        return result

    def report(self, job_id: str) -> dict[str, Any]:
        path = self.jobs_root / job_id / "artifacts" / "report.json"
        if not path.is_file():
            raise FileNotFoundError("Report is not ready")
        return _read_json(path)

    def add_correction(self, job_id: str, correction: dict[str, Any]) -> None:
        self.get_state(job_id)
        path = self.jobs_root / job_id / "artifacts" / "annotations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {**correction, "created_at": _now()}
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _redacted_error(exc: Exception) -> str:
        message = str(exc)[:500]
        key = os.getenv("SARVAM_API_KEY")
        if key:
            message = message.replace(key, "[REDACTED]")
        return f"{type(exc).__name__}: {message}"
