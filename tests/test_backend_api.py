from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app
from backend.models.api import CreateJobRequest
from backend.services.job_service import JobService, normalize_youtube_url


class BackendApiTests(unittest.TestCase):
    def test_youtube_url_normalization(self) -> None:
        expected = "hkvERAuoaI8"
        for value in (
            f"https://youtube.com/shorts/{expected}",
            f"https://youtube.com/watch?v={expected}",
            f"https://youtu.be/{expected}",
        ):
            normalized, video_id = normalize_youtube_url(value)
            self.assertEqual(video_id, expected)
            self.assertEqual(
                normalized, f"https://www.youtube.com/watch?v={expected}"
            )

    def test_create_job_requires_creator_authorisation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir))
            with patch("backend.routes.jobs.service", service):
                client = TestClient(app)
                response = client.post(
                    "/api/jobs",
                    json={
                        "source_url": "https://youtu.be/hkvERAuoaI8",
                        "creator_authorised": False,
                        "target_language": "te-IN",
                    },
                )
                self.assertEqual(response.status_code, 422)

    def test_upload_creates_filesystem_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            root = Path(raw_dir)
            service = JobService(root)
            with patch("backend.routes.jobs.service", service):
                client = TestClient(app)
                response = client.post(
                    "/api/jobs/upload",
                    data={
                        "creator_authorised": "true",
                        "target_language": "te-IN",
                        "source_language": "auto",
                    },
                    files={
                        "source_file": ("source.mp4", b"local-mp4", "video/mp4"),
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertTrue(body["has_source"])
                self.assertFalse(body["has_target"])
                self.assertEqual(body["target_language"], "te-IN")
                job_dir = root / body["job_id"]
                self.assertTrue((job_dir / "inputs" / "source.mp4").is_file())
                self.assertFalse(any((job_dir / "inputs").glob("target.*")))

    def test_capabilities_are_backend_owned_and_separate(self) -> None:
        client = TestClient(app)
        response = client.get("/api/capabilities")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("te-IN", body["source_stt_languages"])
        self.assertIn("od-IN", body["enabled_dubbing_target_languages"])
        self.assertFalse(body["automatic_dubbing_available"])
        self.assertEqual(body["dubbing_mode"], "manual_creator_studio")

    def test_target_must_be_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir))
            with patch("backend.routes.jobs.service", service):
                response = TestClient(app).post(
                    "/api/jobs",
                    json={"creator_authorised": True, "target_language": "xx-XX"},
                )
        self.assertEqual(response.status_code, 422)

    def test_auto_source_jobs_accept_enabled_language_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            service = JobService(Path(raw_dir))
            with patch("backend.routes.jobs.service", service):
                client = TestClient(app)
                for target in ("te-IN", "hi-IN", "od-IN"):
                    response = client.post(
                        "/api/jobs",
                        json={
                            "creator_authorised": True,
                            "source_language": "auto",
                            "target_language": target,
                            "expected_speakers": None,
                        },
                    )
                    self.assertEqual(response.status_code, 201, response.text)

    def test_dubbed_artifact_only_resumes_awaiting_dubbing_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            root = Path(raw_dir)
            service = JobService(root)
            created = service.create_job(
                CreateJobRequest(
                    creator_authorised=True, target_language="te-IN", source_language="en-IN"
                )
            )
            state = service.get_state(created.job_id)
            state.update(status="awaiting_dubbing", has_source=True)
            service._store_state(state)
            with patch("backend.routes.jobs.service", service), patch.object(service, "run_job"):
                response = TestClient(app).post(
                    f"/api/jobs/{created.job_id}/dubbed-artifact",
                    files={"target_file": ("dub.wav", b"local-wav", "audio/wav")},
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "queued")
            self.assertTrue((root / created.job_id / "inputs" / "target.wav").is_file())
