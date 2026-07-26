from __future__ import annotations

from shorts_fidelity_judge.judge import semantic_review
from shorts_fidelity_judge.models import Finding, Severity, Status


class Provider:
    def review(self, payload: dict[str, object]) -> str:
        return '{"status":"preserved","findings":[],"rationale":"looks fine"}'


def test_number_finding_cannot_be_overridden() -> None:
    finding = Finding(category="number_or_unit_mismatch", severity=Severity.CRITICAL, source_text="1000 hp", target_text="1300 hp", evidence="different", uncertainty="none", recommended_action="review")
    verdict = semantic_review(Provider(), {}, [finding])
    assert verdict.status is Status.REVIEW_REQUIRED
    assert verdict.findings == [finding]
