from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sarvamai import SarvamAI

from shorts_fidelity_judge.config import load_repository_env

LOG = logging.getLogger(__name__)


class SemanticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alignment_id: str
    category: Literal[
        "source_omission",
        "unsupported_addition",
        "speaker_attribution_drift",
        "register_drift",
        "punchline_drift",
        "unable_to_align",
    ]
    severity: Literal["critical", "high", "medium", "low"]
    source_text: str
    target_text: str
    english_back_translation: str
    evidence: str
    uncertainty: str


class SemanticResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["preserved", "review_required", "unable_to_verify"]
    findings: list[SemanticFinding] = Field(default_factory=list)
    rationale: str


class SemanticJudge(Protocol):
    def review(
        self, payload: dict[str, Any], deterministic: list[dict[str, Any]]
    ) -> SemanticResult: ...


class SarvamSemanticJudge:
    def __init__(
        self,
        cache_dir: Path,
        *,
        model: str = "sarvam-30b",
        env_path: Path | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.model = model
        self.env_path = env_path

    def review(
        self, payload: dict[str, Any], deterministic: list[dict[str, Any]]
    ) -> SemanticResult:
        judge_input = {
            "model": self.model,
            "payload": payload,
            "deterministic_findings": deterministic,
            "contract_version": "1.0",
        }
        digest = hashlib.sha256(
            json.dumps(
                judge_input, ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        cache_path = self.cache_dir / f"{digest}.json"
        if cache_path.is_file():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            LOG.info("Using cached semantic review %s", cache_path.name)
            return SemanticResult.model_validate(cached["result"])

        load_repository_env(self.env_path)
        key = os.getenv("SARVAM_API_KEY")
        if not key:
            raise RuntimeError(
                "SARVAM_API_KEY is required when no semantic-judge cache exists"
            )
        schema = SemanticResult.model_json_schema()
        prompt = {
            "instruction": (
                "Review source-to-dub semantic fidelity. Only add evidence-backed "
                "semantic findings. Do not reassess or override deterministic number, "
                "unit, automotive-term, or protected-entity findings. Return unable_to_verify "
                "when the evidence is insufficient. This is a review aid, not certification."
            ),
            **judge_input,
        }
        client = SarvamAI(api_subscription_key=key)
        response = client.chat.completions(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                }
            ],
            temperature=0,
            max_tokens=3000,
            request_options={
                "additional_body_parameters": {
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "fidelity_review",
                            "strict": True,
                            "schema": schema,
                        },
                    }
                }
            },
        )
        content = response.choices[0].message.content
        result = SemanticResult.model_validate_json(content)
        envelope = {
            "request": {
                "input_sha256": digest,
                "model": self.model,
                "contract_version": "1.0",
            },
            "provider": {
                "response_id": getattr(response, "id", None),
                "model": getattr(response, "model", self.model),
            },
            "result": result.model_dump(mode="json"),
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return result
