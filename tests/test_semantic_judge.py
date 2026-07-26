from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.semantic_judge import SarvamSemanticJudge


class SemanticJudgeTests(unittest.TestCase):
    def test_cached_result_requires_no_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            cache = Path(raw_dir)
            payload = {"alignments": []}
            deterministic: list[dict[str, object]] = []
            judge_input = {
                "model": "sarvam-30b",
                "payload": payload,
                "deterministic_findings": deterministic,
                "contract_version": "1.0",
            }
            digest = hashlib.sha256(
                json.dumps(
                    judge_input, ensure_ascii=False, sort_keys=True
                ).encode("utf-8")
            ).hexdigest()
            (cache / f"{digest}.json").write_text(
                json.dumps(
                    {
                        "result": {
                            "verdict": "unable_to_verify",
                            "findings": [],
                            "rationale": "Cached.",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                result = SarvamSemanticJudge(
                    cache, env_path=cache / ".missing"
                ).review(payload, deterministic)
            self.assertEqual(result.verdict, "unable_to_verify")
