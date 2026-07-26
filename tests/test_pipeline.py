import json
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from shorts_fidelity_judge.audio import inspect_wav
from shorts_fidelity_judge.cli import evaluate
from shorts_fidelity_judge.stt import SarvamSTTAdapter


class PipelineTests(unittest.TestCase):
    def test_audio_inspection_detects_duration(self):
        with tempfile.TemporaryDirectory() as raw_dir:
            wav = Path(raw_dir) / "silence.wav"
            with wave.open(str(wav), "wb") as out:
                out.setnchannels(1); out.setsampwidth(2); out.setframerate(8000); out.writeframes(b"\0\0" * 8000)
            result = inspect_wav(wav)
            self.assertEqual(result["duration_seconds"], 1)
            self.assertTrue(result["long_pauses"])

    def test_fixture_pipeline_offline(self):
        with tempfile.TemporaryDirectory() as raw_dir:
            output = Path(raw_dir)
            self.assertEqual(evaluate(Path("benchmark/fixtures/mat_armstrong_manifest.json"), output, Path("benchmark/glossary.yaml")), 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(str(report["status"]), "unable_to_verify")
            self.assertTrue((output / "report.html").exists())
            self.assertTrue((output / "annotations.jsonl").exists())

    def test_stt_cache_prevents_network_request(self):
        with tempfile.TemporaryDirectory() as raw_dir:
            root = Path(raw_dir)
            audio = root / "dub.wav"
            audio.write_bytes(b"local-only-test-audio")
            cache = root / "cache"; cache.mkdir()
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            (cache / f"{digest}.json").write_text(json.dumps({"transcript": "cached result", "language_code": "te-IN"}))
            transcript = SarvamSTTAdapter(cache).transcribe(audio, "te-IN")
            self.assertEqual(transcript.transcript, "cached result")
            self.assertEqual(transcript.provenance, "sarvam_stt")
