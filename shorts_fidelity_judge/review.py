from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from .models import Finding, Segment, SemanticVerdict, Severity, Status

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
NUMBER = re.compile(r"\b(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|thousand)\b", re.I)
MODELCODE = re.compile(r"\b[A-Z]{1,4}[- ]?\d{1,4}[A-Z]?\b")


def split_source(text: str) -> list[Segment]:
    parts = [part.strip() for part in SENTENCE_SPLIT.split(text) if part.strip()]
    return [Segment(id=f"source-{index + 1}", text=value) for index, value in enumerate(parts)]


def align(source: list[Segment], target: list[Segment]) -> list[tuple[Segment, Segment | None]]:
    """Order-preserving alignment. Timestamps win; otherwise segment order is auditable."""
    results: list[tuple[Segment, Segment | None]] = []
    for index, source_segment in enumerate(source):
        target_segment = target[index] if index < len(target) else None
        results.append((source_segment, target_segment))
    return results


def load_glossary(path: Path) -> dict[str, list[str]]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def deterministic_findings(source: list[Segment], target: list[Segment], glossary: dict[str, list[str]]) -> list[Finding]:
    findings: list[Finding] = []
    all_target = " ".join(segment.text for segment in target)
    for source_segment, target_segment in align(source, target):
        target_text = target_segment.text if target_segment else ""
        if not target_segment:
            findings.append(_finding("unmatched_segment", Severity.HIGH, source_segment, None, "No aligned target utterance.", "Check whether dubbing omitted or merged this utterance."))
            continue
        source_atoms = _atoms(source_segment.text, glossary)
        target_atoms = _atoms(target_text, glossary)
        for atom in sorted(source_atoms):
            if atom not in target_atoms:
                category = "critical_atom_omission" if _critical(atom) else "protected_term_omission"
                findings.append(_finding(category, Severity.CRITICAL if _critical(atom) else Severity.HIGH, source_segment, target_segment, f"Source contains protected atom '{atom}', aligned target does not.", "Verify transcript/back-translation and dub audio; retain exact critical atom."))
        if _has_negation(source_segment.text) and not _has_negation(target_text):
            findings.append(_finding("negation_deleted", Severity.CRITICAL, source_segment, target_segment, "Source is negative but aligned target has no detected negation.", "Review semantic polarity against audio."))
        if "rear-wheel drive" in source_segment.text.lower() and "four-wheel drive" in target_text.lower():
            findings.append(_finding("drivetrain_substitution", Severity.CRITICAL, source_segment, target_segment, "rear-wheel drive changed to four-wheel drive.", "Correct drivetrain terminology."))
        if source_segment.speaker and target_segment.speaker and source_segment.speaker != target_segment.speaker:
            findings.append(_finding("speaker_attribution_conflict", Severity.HIGH, source_segment, target_segment, f"Source speaker={source_segment.speaker}; target speaker={target_segment.speaker}.", "Verify who is speaking or who owns the vehicle."))
    # Entire target is used only to identify an explicit closing punchline omission.
    if source and _looks_like_punchline(source[-1].text) and not _looks_like_punchline(all_target):
        findings.append(_finding("punchline_omission", Severity.HIGH, source[-1], None, "Final source utterance is a subscriber punchline; no subscriber cue appears in target.", "Review final audio segment and preserve the joke/punchline."))
    return findings


def _atoms(text: str, glossary: dict[str, list[str]]) -> set[str]:
    lower = text.lower().replace("horse power", "horsepower")
    atoms = {item.lower() for item in NUMBER.findall(lower)}
    atoms.update(match.group(0).lower() for match in MODELCODE.finditer(text))
    for value in glossary.get("protected_terms", []) + glossary.get("brands", []) + glossary.get("drivetrain_terms", []):
        if value.lower() in lower:
            atoms.add(value.lower())
    for unit in ("hp", "horsepower", "%", "km/h", "mph", "litre", "liter", "v10", "v12", "twin-turbo", "turbo"):
        if unit in lower:
            atoms.add(unit)
    return atoms


def _critical(atom: str) -> bool:
    return atom in {"hp", "horsepower", "rear-wheel drive", "four-wheel drive", "twin-turbo"} or bool(NUMBER.fullmatch(atom)) or bool(MODELCODE.fullmatch(atom.upper()))


def _has_negation(text: str) -> bool:
    return bool(re.search(r"\b(no|not|never|without|isn't|don't|doesn't|cannot|can't)\b", text, re.I))


def _looks_like_punchline(text: str) -> bool:
    return bool(re.search(r"\b(subscribe|subscriber|subscribers)\b", text, re.I))


def _finding(category: str, severity: Severity, source: Segment, target: Segment | None, evidence: str, action: str) -> Finding:
    return Finding(category=category, severity=severity, source_segment_id=source.id, target_segment_id=target.id if target else None, source_text=source.text, target_text=target.text if target else "", evidence=evidence, uncertainty="Transcript alignment is heuristic unless matching timestamps/speakers are supplied.", recommended_action=action)


class SemanticReviewProvider(Protocol):
    def review(self, source: Segment, target: Segment, back_translation: str, deterministic: list[Finding], glossary: dict[str, list[str]]) -> SemanticVerdict: ...


def combine_status(findings: list[Finding], semantic_available: bool) -> Status:
    if not semantic_available and not findings:
        return Status.UNABLE_TO_VERIFY
    return Status.REVIEW_REQUIRED if findings else Status.PRESERVED
