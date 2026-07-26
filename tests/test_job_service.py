from __future__ import annotations

import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from backend.models.api import CreateJobRequest
from backend.services.job_service import JobService
from backend.services.semantic_judge import SemanticResult
from shorts_fidelity_judge.models import Segment, TargetTranscript


class _FakeSTT:
    def __init__(self, _cache: Path) -> None:
        pass

    def transcribe(self, _audio: Path, language: str, mode: str = "transcribe", **_kwargs):
        if language in {"en-IN", "unknown"} and mode == "transcribe":
            values = [
                ("I built a Lamborghini Gallardo.", 0, 2),
                ("Stradman does.", 2, 3),
                ("Mine has 1000 horsepower.", 3, 4),
                ("His has 1300 horsepower.", 4, 5),
                ("It is rear-wheel drive.", 5, 6),
                ("He has more subscribers than you.", 6, 7),
            ]
        elif mode == "translate":
            values = [
                ("I built a Lamborghini car.", 0, 2),
                ("Hit me on my nose.", 2, 3),
                ("Mine has 1000 horsepower and his has 1300 horsepower.", 3, 5),
                ("It is monster wheel drive.", 5, 6),
                ("He has more subscribers than you.", 6, 7),
            ]
        else:
            values = [
                ("నేను లంబోర్ఘిని కారు నిర్మించాను.", 0, 2),
                ("నా ముక్కు మీద కొట్టు", 2, 3),
                ("నాది 1000 హార్స్ పవర్, అతనిది 1300 హార్స్ పవర్.", 3, 5),
                ("ఇది మాన్స్టర్ వీల్ డ్రైవ్.", 5, 6),
                ("అతనికి నీకంటే ఎక్కువ సబ్‌స్క్రైబర్లు ఉన్నారు.", 6, 7),
            ]
        segments = [
            Segment(
                id=f"segment-{index}",
                text=text,
                start_seconds=start,
                end_seconds=end,
                speaker="SPEAKER_00",
            )
            for index, (text, start, end) in enumerate(values, 1)
        ]
        metadata = {"transcript": "provider response"}
        if language == "unknown":
            metadata["metadata"] = {
                "detected_language_code": "en-IN", "language_probability": 0.94
            }
        return TargetTranscript(
            transcript=" ".join(item.text for item in segments),
            segments=segments,
            provenance="sarvam_stt",
            raw_response=metadata,
        )


class _FakeJudge:
    def __init__(self, _cache: Path) -> None:
        pass

    def review(self, _payload, _deterministic) -> SemanticResult:
        return SemanticResult(
            verdict="review_required",
            findings=[],
            rationale="Deterministic findings require review.",
        )


def _write_silence(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0\0" * 16_000)


class JobServiceTests(unittest.TestCase):
    def test_job_errors_redact_configured_api_key(self) -> None:
        with patch.dict(os.environ, {"SARVAM_API_KEY": "secret-value"}):
            message = JobService._redacted_error(
                RuntimeError("request failed for secret-value")
            )
        self.assertNotIn("secret-value", message)
        self.assertIn("[REDACTED]", message)

    def test_number_words_are_normalized(self) -> None:
        self.assertEqual(JobService._numbers("a thousand horsepower"), {"1000"})
        self.assertEqual(JobService._numbers("thirteen hundred hp"), {"1300"})

    def test_complete_unicode_report_and_many_to_many_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir) / "jobs")
            job = service.create_job(
                CreateJobRequest(
                    creator_authorised=True,
                    source_language="en-IN",
                    target_language="te-IN",
                    expected_speakers=2,
                )
            )
            job_dir = service.jobs_root / job.job_id
            (job_dir / "inputs" / "source.mp4").write_bytes(b"source")
            (job_dir / "inputs" / "target.wav").write_bytes(b"target")
            state = service.get_state(job.job_id)
            state.update(has_source=True, has_target=True)
            service._store_state(state)

            def fake_extract(_source: Path, target: Path) -> None:
                _write_silence(target)

            with patch(
                "backend.services.job_service.SarvamSTTAdapter", _FakeSTT
            ), patch(
                "backend.services.job_service.SarvamSemanticJudge", _FakeJudge
            ), patch.object(JobService, "_extract_audio", side_effect=fake_extract):
                service.run_job(job.job_id)

            completed = service.get_state(job.job_id)
            self.assertEqual(completed["status"], "complete")
            report = service.report(job.job_id)
            categories = {item["category"] for item in report["findings"]}
            self.assertIn("protected_entity_drift", categories)
            self.assertIn("unsupported_addition", categories)
            self.assertIn("automotive_term_drift", categories)
            self.assertIn("number_preserved", categories)
            self.assertIn("punchline_preserved", categories)
            self.assertIn("నా ముక్కు మీద కొట్టు", str(report))
            merged = [
                item
                for item in report["alignments"]
                if "1000" in item["english_back_translation"]
            ]
            self.assertEqual(len(merged), 2)
            unsupported = [
                item
                for item in report["findings"]
                if item["category"] == "unsupported_addition"
            ]
            self.assertEqual(len(unsupported), 1)

    def test_auto_detected_source_reaches_manual_dubbing_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir) / "jobs")
            job = service.create_job(CreateJobRequest(creator_authorised=True, target_language="te-IN"))
            job_dir = service.jobs_root / job.job_id
            (job_dir / "inputs" / "source.mp4").write_bytes(b"source")
            state = service.get_state(job.job_id)
            state["has_source"] = True
            service._store_state(state)

            with patch("backend.services.job_service.SarvamSTTAdapter", _FakeSTT), patch.object(JobService, "_extract_audio", side_effect=lambda _source, target: _write_silence(target)):
                service.run_job(job.job_id)

            paused = service.get_state(job.job_id)
            self.assertEqual(paused["status"], "awaiting_dubbing")
            self.assertEqual(paused["detected_source_language"], "en-IN")
            self.assertEqual(paused["source_language"], "en-IN")
            detection = (job_dir / "artifacts" / "source_language_detection.json").read_text()
            self.assertIn("sarvam_saaras_v3_batch_stt_metadata", detection)

    def test_low_confidence_detection_requires_confirmation(self) -> None:
        class LowConfidenceSTT(_FakeSTT):
            def transcribe(self, *args, **kwargs):
                transcript = super().transcribe(*args, **kwargs)
                transcript.raw_response = {
                    "metadata": {"detected_language_code": "hi-IN", "language_probability": 0.2}
                }
                return transcript

        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir) / "jobs")
            job = service.create_job(CreateJobRequest(creator_authorised=True, target_language="te-IN"))
            job_dir = service.jobs_root / job.job_id
            (job_dir / "inputs" / "source.mp4").write_bytes(b"source")
            state = service.get_state(job.job_id)
            state["has_source"] = True
            service._store_state(state)
            with patch("backend.services.job_service.SarvamSTTAdapter", LowConfidenceSTT), patch.object(JobService, "_extract_audio", side_effect=lambda _source, target: _write_silence(target)):
                service.run_job(job.job_id)
            self.assertEqual(service.get_state(job.job_id)["status"], "source_language_confirmation_required")

    def test_actual_asr_phonetics_are_evidence_not_silent_rewrites(self) -> None:
        alignments = [
            {
                "alignment_id": "align-001",
                "state": "aligned",
                "source_segment_ids": ["source-001"],
                "target_segment_ids": ["target-001"],
                "source_text": "I built a Lamborghini Guardo.",
                "target_text": "లాంబోర్కిని",
                "english_back_translation": "I built a Lamborghini.",
            },
            {
                "alignment_id": "align-002",
                "state": "aligned",
                "source_segment_ids": ["source-002"],
                "target_segment_ids": ["target-002"],
                "source_text": "Strict means",
                "target_text": "నా ముక్కు మీద కొట్టు",
                "english_back_translation": "Hit me on the nose.",
            },
            {
                "alignment_id": "align-003",
                "state": "aligned",
                "source_segment_ids": ["source-003"],
                "target_segment_ids": ["target-003"],
                "source_text": "Month's we will drive.",
                "target_text": "మాన్స్టర్ వీల్ డ్రైవ్",
                "english_back_translation": "Monster Wheel Drive.",
            },
            {
                "alignment_id": "align-004",
                "state": "aligned",
                "source_segment_ids": ["source-004"],
                "target_segment_ids": ["target-003"],
                "source_text": "His is four-wheel drive.",
                "target_text": "ఫోర్ వీల్ డ్రైవ్",
                "english_back_translation": "Monster Wheel Drive. His is Four Wheel Drive.",
            },
        ]
        findings = JobService._findings(alignments)
        evidence = " ".join(item["evidence"] for item in findings)
        self.assertIn("Lamborghini Gallardo", evidence)
        self.assertIn("Stradman", evidence)
        self.assertIn("rear-wheel drive", evidence)
        self.assertFalse(
            any(
                item["category"] == "automotive_term_drift"
                and item["source_text"] == "His is four-wheel drive."
                for item in findings
            )
        )
