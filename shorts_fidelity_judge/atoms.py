"""Deterministic checks for protected facts and meaning-critical constructs."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .alignment import AlignedPair
from .models import Finding, Severity

NUMBER = re.compile(r"\b\d+(?:[,.]\d+)?\b")
NEGATION = re.compile(r"\b(?:no|not|never|isn't|wasn't|don't|doesn't|without|can't|won't)\b", re.I)
CAUSE = re.compile(r"\b(?:because|so|therefore|after|before|then)\b", re.I)
MODEL_CODE = re.compile(r"\b[A-Z]{1,4}[ -]?\d{1,4}[A-Z]?\b")


def load_glossary(path: Path) -> dict[str, list[str]]:
    data: dict[str, list[str]] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def extract_atoms(text: str, glossary: dict[str, list[str]]) -> dict[str, list[str]]:
    lower = text.lower()
    terms = glossary.get("protected_terms", []) + glossary.get("brands", []) + glossary.get("drivetrain_terms", [])
    return {
        "numbers": NUMBER.findall(lower),
        "terms": [term for term in terms if term.lower() in lower],
        "model_codes": MODEL_CODE.findall(text),
        "negation": NEGATION.findall(lower),
        "sequence_cause": CAUSE.findall(lower),
    }


def deterministic_findings(pairs: list[AlignedPair], glossary: dict[str, list[str]]) -> list[Finding]:
    findings: list[Finding] = []
    for pair in pairs:
        if pair.source is None:
            findings.append(_finding("unmatched_target_segment", Severity.MEDIUM, pair, "Target utterance has no aligned source utterance."))
            continue
        if pair.target is None:
            severity = Severity.HIGH if _is_punchline(pair.source.text) else Severity.MEDIUM
            category = "punchline_omission" if _is_punchline(pair.source.text) else "unmatched_source_segment"
            findings.append(_finding(category, severity, pair, "Source utterance has no aligned target utterance."))
            continue
        source, target = extract_atoms(pair.source.text, glossary), extract_atoms(pair.target.text, glossary)
        for category in ("numbers", "terms", "model_codes"):
            missing = sorted(set(source[category]) - set(target[category]))
            extra = sorted(set(target[category]) - set(source[category]))
            if missing or extra:
                label = "number_or_unit_mismatch" if category == "numbers" else f"{category}_mismatch"
                findings.append(_finding(label, Severity.CRITICAL if category == "numbers" else Severity.HIGH, pair, f"Source {category}: {source[category]}; target {category}: {target[category]}."))
        if bool(source["negation"]) != bool(target["negation"]):
            findings.append(_finding("negation_mismatch", Severity.HIGH, pair, "Negation presence differs between source and target."))
        if bool(source["sequence_cause"]) != bool(target["sequence_cause"]):
            findings.append(_finding("sequence_or_cause_mismatch", Severity.MEDIUM, pair, "Sequence/cause cue presence differs between source and target."))
        if pair.source.speaker and pair.target.speaker and pair.source.speaker.casefold() != pair.target.speaker.casefold():
            findings.append(_finding("speaker_attribution_conflict", Severity.HIGH, pair, f"Source speaker {pair.source.speaker!r} differs from target speaker {pair.target.speaker!r}."))
    return findings


def _is_punchline(text: str) -> bool:
    return bool(re.search(r"\b(subscribe|subscriber|like and subscribe|punchline)\b", text, re.I))


def _finding(category: str, severity: Severity, pair: AlignedPair, evidence: str) -> Finding:
    return Finding(category=category, severity=severity, source_segment_id=pair.source.id if pair.source else None, target_segment_id=pair.target.id if pair.target else None, source_text=pair.source.text if pair.source else "", target_text=pair.target.text if pair.target else "", evidence=evidence, uncertainty="Lexical alignment and supplied back-translation may not capture an acceptable idiomatic adaptation.", recommended_action="Human reviewer should compare the corresponding audio and transcript.")
