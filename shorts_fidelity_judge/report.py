from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .alignment import AlignedPair
from .models import Finding, Status


def overall_status(findings: list[Finding], audio_available: bool) -> Status:
    if not audio_available:
        return Status.UNABLE_TO_VERIFY
    return Status.REVIEW_REQUIRED if findings else Status.PRESERVED


def write_report(output_dir: Path, metadata: dict[str, Any], audio: dict[str, Any], pairs: list[AlignedPair], findings: list[Finding], deterministic_checks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    status = overall_status(findings, bool(audio.get("available")))
    report = {"status": status, "overall_status": status, "metadata": metadata, "audio_inspection": audio,
              "alignment": [{"source": p.source.model_dump() if p.source else None, "target": p.target.model_dump() if p.target else None, "score": round(p.score, 3)} for p in pairs],
              "findings": [f.model_dump(mode="json") for f in findings],
              "deterministic_checks": deterministic_checks or [],
              "timeline": [{"source_segment_id": f.source_segment_id, "target_segment_id": f.target_segment_id, "category": f.category, "severity": f.severity} for f in findings]}
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    rows = "".join(f"<tr><td>{html.escape(f.category)}</td><td>{html.escape(str(f.severity))}</td><td>{html.escape(f.source_text)}</td><td>{html.escape(f.target_text)}</td><td>{html.escape(f.evidence)}</td><td>{html.escape(f.recommended_action)}</td></tr>" for f in findings)
    page = f"<!doctype html><html><head><meta charset='utf-8'><title>DubPatch</title><style>body{{font-family:sans-serif;margin:2rem}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.5rem;vertical-align:top}}</style></head><body><h1>DubPatch</h1><p>Status: <strong>{status}</strong></p><p>Timeline: {html.escape(', '.join(f.source_segment_id or f.target_segment_id or 'unmatched' for f in findings)) or 'No flagged segments'}</p><table><tr><th>Category</th><th>Severity</th><th>Source</th><th>Target/back-translation</th><th>Evidence</th><th>Action</th></tr>{rows}</table></body></html>"
    (output_dir / "report.html").write_text(page, encoding="utf-8")
    return report
