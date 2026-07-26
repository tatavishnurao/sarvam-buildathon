"""Transparent lexical alignment; it reports uncertainty rather than inventing it."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Segment


@dataclass(frozen=True)
class AlignedPair:
    source: Segment | None
    target: Segment | None
    score: float


def align_segments(source: list[Segment], target: list[Segment]) -> list[AlignedPair]:
    """Monotonic greedy alignment over source/back-translation utterances."""
    pairs: list[AlignedPair] = []
    cursor = 0
    for source_segment in source:
        best_index, best_score = cursor, 0.0
        for index in range(cursor, min(len(target), cursor + 4)):
            score = _similarity(source_segment.text, target[index].text)
            if score > best_score:
                best_index, best_score = index, score
        if best_score >= 0.12 and cursor < len(target):
            pairs.append(AlignedPair(source_segment, target[best_index], best_score))
            cursor = best_index + 1
        else:
            pairs.append(AlignedPair(source_segment, None, 0.0))
    pairs.extend(AlignedPair(None, item, 0.0) for item in target[cursor:])
    return pairs


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))
