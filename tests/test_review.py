import unittest

from shorts_fidelity_judge.models import Segment, Severity
from shorts_fidelity_judge.review import deterministic_findings

GLOSSARY = {"protected_terms": ["Lamborghini Gallardo", "Stradman", "twin-turbo", "rear-wheel drive", "four-wheel drive"], "brands": ["Lamborghini"], "drivetrain_terms": ["rear-wheel drive", "four-wheel drive"]}


def check(source: str, target: str, speaker: str | None = None, target_speaker: str | None = None):
    return deterministic_findings([Segment(id="s", text=source, speaker=speaker)], [Segment(id="t", text=target, speaker=target_speaker)], GLOSSARY)


def categories(findings): return {item.category for item in findings}


class DeterministicReviewTests(unittest.TestCase):
    def test_1000_vs_1300_horsepower(self):
        self.assertIn("critical_atom_omission", categories(check("It makes 1000 hp.", "It makes 1300 hp.")))

    def test_rear_wheel_vs_four_wheel_drive(self):
        findings = check("It is rear-wheel drive.", "It is four-wheel drive.")
        self.assertIn("drivetrain_substitution", categories(findings))
        self.assertTrue(any(item.severity == Severity.CRITICAL for item in findings))

    def test_negation_deletion(self):
        self.assertIn("negation_deleted", categories(check("It is not stock.", "It is stock.")))

    def test_model_name_preservation(self):
        self.assertIn("protected_term_omission", categories(check("This is a Lamborghini Gallardo.", "This is a Lamborghini.")))

    def test_o_vs_zero_is_not_silently_equivalent(self):
        self.assertIn("critical_atom_omission", categories(check("It has 0 leaks.", "It has O leaks.")))

    def test_punchline_omission(self):
        findings = deterministic_findings([Segment(id="s", text="Subscribe for the final surprise.")], [Segment(id="t", text="The car is fast.")], GLOSSARY)
        self.assertIn("punchline_omission", categories(findings))

    def test_unmatched_speaker_attribution(self):
        self.assertIn("speaker_attribution_conflict", categories(check("Mat owns this car.", "Mat owns this car.", "Mat", "Stradman")))
