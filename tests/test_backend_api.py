from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app
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
                        "source_language": "en-IN",
                        "expected_speakers": "2",
                    },
                    files={
                        "source_file": ("source.mp4", b"local-mp4", "video/mp4"),
                        "target_file": ("target.wav", b"local-wav", "audio/wav"),
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertTrue(body["has_source"])
                self.assertTrue(body["has_target"])
                self.assertEqual(body["target_language"], "te-IN")
                job_dir = root / body["job_id"]
                self.assertTrue((job_dir / "inputs" / "source.mp4").is_file())
                self.assertTrue((job_dir / "inputs" / "target.wav").is_file())
