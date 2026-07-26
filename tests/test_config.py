from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shorts_fidelity_judge.config import load_repository_env
from shorts_fidelity_judge.stt import SarvamSTTAdapter, SarvamSTTError


class EnvironmentSafetyTests(unittest.TestCase):
    def test_shell_value_takes_precedence_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            dotenv = Path(raw_dir) / ".env"
            secret = "should-never-appear"
            dotenv.write_text(f"SARVAM_API_KEY={secret}\n", encoding="utf-8")
            output = io.StringIO()
            with patch.dict(os.environ, {"SARVAM_API_KEY": "shell-wins"}, clear=False):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    load_repository_env(dotenv)
                self.assertEqual(os.environ["SARVAM_API_KEY"], "shell-wins")
            self.assertNotIn(secret, output.getvalue())

    def test_missing_key_has_clear_redacted_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            root = Path(raw_dir)
            audio = root / "audio.wav"
            audio.write_bytes(b"not-sent")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    SarvamSTTError, "SARVAM_API_KEY is required"
                ) as error:
                    SarvamSTTAdapter(root / "cache", env_path=root / ".env").transcribe(
                        audio, "te-IN"
                    )
            self.assertNotIn("not-sent", str(error.exception))
