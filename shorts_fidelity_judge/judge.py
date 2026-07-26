"""Provider-neutral semantic-review contract with strict output validation."""
from __future__ import annotations

from typing import Protocol

from .models import Finding, SemanticVerdict, Status


class SemanticProvider(Protocol):
    def review(self, payload: dict[str, object]) -> str: ...


def semantic_review(provider: SemanticProvider, payload: dict[str, object], deterministic: list[Finding]) -> SemanticVerdict:
    """Validate provider JSON and retain all critical deterministic mismatches."""
    verdict = SemanticVerdict.model_validate_json(provider.review(payload))
    protected = [item for item in deterministic if item.category == "number_or_unit_mismatch"]
    existing = {(item.category, item.source_segment_id) for item in verdict.findings}
    verdict.findings.extend(item for item in protected if (item.category, item.source_segment_id) not in existing)
    if protected:
        verdict.status = Status.REVIEW_REQUIRED
    return verdict
