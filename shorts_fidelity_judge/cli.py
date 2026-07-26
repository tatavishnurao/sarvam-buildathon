from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .alignment import align_segments
from .atoms import deterministic_findings, extract_atoms, load_glossary
from .audio import write_audio_inspection
from .models import Manifest
from .report import write_report
from .stt import SarvamSTTAdapter
from .transcripts import load_source, load_target, segment_text


def evaluate(manifest_path: Path, output: Path, glossary_path: Path = Path("benchmark/glossary.yaml")) -> int:
    """Run the golden path programmatically; return a shell-compatible code."""
    manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    audio = write_audio_inspection(manifest.dubbed_wav, output / "audio_inspection.json") if manifest.dubbed_wav else {"available": False, "reason": "No dubbed WAV supplied"}
    source = load_source(manifest.source_transcript)
    if manifest.target_transcript:
        target = load_target(manifest.target_transcript)
    elif manifest.dubbed_wav and manifest.stt.get("enabled"):
        target = SarvamSTTAdapter(output / "stt-cache").transcribe(manifest.dubbed_wav, manifest.target_language, manifest.stt.get("model", "saaras:v3"))
    else:
        raise ValueError("Provide target_transcript or enable STT with dubbed_wav.")
    alignment_text = target.back_translation or target.transcript
    target_segments = target.segments or segment_text(alignment_text, "target")
    if target.back_translation and not target.segments:
        target_segments = segment_text(target.back_translation, "target")
    pairs = align_segments(source, target_segments)
    glossary = load_glossary(glossary_path)
    findings = deterministic_findings(pairs, glossary)
    checks = [
        {"source_segment_id": pair.source.id, "target_segment_id": pair.target.id if pair.target else None,
         "source_atoms": extract_atoms(pair.source.text, glossary),
         "target_atoms": extract_atoms(pair.target.text, glossary) if pair.target else {},
         "alignment_score": round(pair.score, 3)}
        for pair in pairs if pair.source
    ]
    metadata = manifest.model_dump(mode="json") | {"target_provenance": target.provenance, "has_back_translation": bool(target.back_translation)}
    write_report(output, metadata, audio, pairs, findings, checks)
    (output / "annotations.jsonl").touch(exist_ok=True)
    logging.info("Wrote report for %s to %s", manifest.video_id, output)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first local dub review")
    parser.add_argument("evaluate")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--glossary", type=Path, default=Path("benchmark/glossary.yaml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    evaluate(args.manifest, args.output, args.glossary)


if __name__ == "__main__":
    main()
