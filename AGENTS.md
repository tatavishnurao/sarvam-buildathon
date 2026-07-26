# DubPatch contributor guide

## Scope

This repository evaluates locally supplied dubbed audio and transcripts. It is a
review aid, never an autonomous certification system. Do not download video or
audio, modify source media, add regeneration, add a vector database, or commit
credentials.

## Golden-path rules

- Keep `python3 -m shorts_fidelity_judge evaluate ...` runnable offline.
- Prefer a supplied target transcript for tests. Live STT is opt-in and uses
  `SARVAM_API_KEY`; cache raw API responses by the SHA-256 of the audio.
- Every finding needs evidence and an uncertainty statement.
- Deterministic number, unit, model, and drivetrain mismatches cannot be
  downgraded to preserved by semantic review.
- Treat fixtures as test data, not as claimed ground truth or benchmark scores.

## Code standards

Use Python 3.11+ syntax, type annotations, Pydantic models at external
boundaries, standard-library-first dependencies, and `logging`. Tests must not
need network access. Use `apply_patch` for edits and retain raw API responses
under the configured output/cache directory.
