from __future__ import annotations

from shorts_fidelity_judge.alignment import AlignedPair
from shorts_fidelity_judge.atoms import deterministic_findings
from shorts_fidelity_judge.models import Segment


GLOSSARY = {
    "protected_terms": ["Lamborghini Gallardo", "Stradman", "twin-turbo", "rear-wheel drive", "four-wheel drive"],
    "brands": ["Lamborghini"],
    "drivetrain_terms": ["rear-wheel drive", "four-wheel drive"],
}


def findings(source: str, target: str, source_speaker: str | None = None, target_speaker: str | None = None) -> set[str]:
    pair = AlignedPair(Segment(id="source-1", text=source, speaker=source_speaker), Segment(id="target-1", text=target, speaker=target_speaker), 1.0)
    return {item.category for item in deterministic_findings([pair], GLOSSARY)}


def test_1000_vs_1300_horsepower() -> None:
    assert "number_or_unit_mismatch" in findings("It makes 1000 hp.", "It makes 1300 hp.")


def test_rear_wheel_vs_four_wheel_drive() -> None:
    assert "terms_mismatch" in findings("It is rear-wheel drive.", "It is four-wheel drive.")


def test_negation_deletion() -> None:
    assert "negation_mismatch" in findings("It does not have traction control.", "It has traction control.")


def test_model_name_preservation() -> None:
    assert "terms_mismatch" in findings("The Lamborghini Gallardo arrives.", "The Lamborghini arrives.")


def test_o_and_zero_are_not_silently_equivalent() -> None:
    assert "number_or_unit_mismatch" in findings("It has 0 boost.", "It has O boost.")


def test_omission_of_punchline() -> None:
    pair = AlignedPair(Segment(id="source-1", text="Subscribe for the final reveal."), None, 0.0)
    result = deterministic_findings([pair], GLOSSARY)
    assert result[0].category == "punchline_omission"


def test_unmatched_speaker_attribution() -> None:
    assert "speaker_attribution_conflict" in findings("The Stradman says it is ready.", "Mat says it is ready.", "Stradman", "Mat")
