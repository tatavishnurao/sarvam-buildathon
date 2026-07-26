"""Local transcript loading and intentionally conservative segmentation."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Segment, TargetTranscript


def load_source(path: Path) -> list[Segment]:
    """Read plain UTF-8 source text; optional ``[Speaker]`` labels are retained."""
    content = path.read_text(encoding="utf-8").strip()
    if path.suffix.lower() == ".json":
        data = json.loads(content)
        if isinstance(data, dict) and "segments" in data:
            return [Segment.model_validate(item) for item in data["segments"]]
        if isinstance(data, dict) and "transcript" in data:
            content = str(data["transcript"])
    text = content
    return segment_text(text, "source")


def load_target(path: Path) -> TargetTranscript:
    """Load a human-provided target transcript without sending it anywhere."""
    data = json.loads(path.read_text(encoding="utf-8"))
    transcript = TargetTranscript.model_validate(data)
    if not transcript.segments and transcript.transcript:
        transcript.segments = segment_text(transcript.transcript, "target")
    return transcript


def segment_text(text: str, prefix: str) -> list[Segment]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    segments: list[Segment] = []
    speaker: str | None = None
    for part in parts:
        part = part.strip()
        if not part:
            continue
        label = re.match(r"^\[([^\]]+)\]\s*", part)
        if label:
            speaker = label.group(1).strip()
            part = part[label.end():].strip()
        if part:
            segments.append(Segment(id=f"{prefix}-{len(segments) + 1}", text=part, speaker=speaker))
    return segments
