# Architecture

`Shorts Fidelity Judge` is a local, evidence-first pipeline for deciding whether
a Sarvam-dubbed automotive short is **preserved**, **review_required**, or
**unable_to_verify**. It deliberately does not calculate a universal accuracy
score and cannot certify a dub without reviewer judgement.

## Flow

```text
manifest + English transcript + local WAV
        |                         |
        |                    audio inspection
        v                         v
manual target transcript OR Sarvam STT (content-address cache)
        |
semantic source segmentation + target/back-translation segmentation
        |
deterministic protected-atom and discourse checks <--- glossary
        |
provider-neutral semantic judge (optional; strict Pydantic JSON)
        |
report.json + report.html + annotation JSONL
```

## Trust boundaries

The manifest references only local paths. The STT adapter is the sole network
boundary; it requires `SARVAM_API_KEY`, uses a timeout and bounded retry, and
writes the complete raw response before downstream use. A manually supplied
target transcript is used unchanged and carries its provenance into the report.

Deterministic checks are authoritative for critical atoms: numbers, units,
currency, model codes, protected terminology, drivetrains, and named entities.
An LLM can add semantic evidence or uncertainty but cannot erase such a mismatch.
If no semantic provider is configured, the output remains a useful deterministic
review report.

## Artifacts

- `audio_inspection.json`: WAV fields, peak, RMS, optional ffmpeg ebur128
  integrated loudness, and pauses.
- `stt-cache/<sha256>.json`: immutable full Sarvam response plus non-secret
  request metadata. Cache hits do not upload the audio again.
- `report.json` / `report.html`: inputs, alignment, findings, status, evidence.
- `annotations.jsonl`: reviewer decisions. Precision is true issues divided by
  labels that can be judged; review compression is reviewed issues divided by
  automatically raised issues.

Missing audio, timestamps, or translation is represented as uncertainty, never
silently inferred.
