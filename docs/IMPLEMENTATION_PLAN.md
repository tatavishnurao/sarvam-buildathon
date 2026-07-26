# Phased implementation plan

1. **Contracts and audit** — define manifest, glossary, artifacts, local-only
   boundary, and acceptance fixture. **Complete.**
2. **Offline golden path** — inspect WAV when supplied; ingest manual transcript;
   align segments; deterministic atom/discourse checks; write JSON/HTML and an
   annotation JSONL; add offline tests. **Complete with the repository test
   synthetic contract fixture; replace it with the supplied Mat Armstrong assets
   before treating any output as a real evaluation.**
3. **Live ingestion and semantic review** — enable content-addressed Sarvam STT
   and a configured provider-neutral semantic judge; validate/reject invalid JSON.
   **Implemented but intentionally not exercised by offline tests.**
4. **Reviewer operation** — run the local review UI against a report, collect
   labels, and monitor precision/compression. **Implemented as a dependency-free
   local web UI; validate with real reviewer data.**
5. **Pilot calibration** — run the actual supplied Mat Armstrong WAV/transcript,
   inspect report evidence with a human, correct glossary/rules, then only expand
   to more cases. **Blocked pending supplied source and dubbed media.**
