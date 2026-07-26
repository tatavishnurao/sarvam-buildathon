# Shorts Fidelity Judge

Evidence-first local review for Sarvam-dubbed automotive Shorts. It produces
`preserved`, `review_required`, or `unable_to_verify`; it never emits a universal
accuracy score or autonomous certification.

Run the fully offline synthetic acceptance-shaped fixture with:

```sh
./scripts/run_mat_armstrong_fixture.sh
python3 -m unittest discover -s tests -v
```

Results are written to `output/mat_armstrong_fixture/`. The fixture is not a
real Mat Armstrong transcript or Telugu dub; see its notice before replacing it
with supplied local source transcript and WAV files. For real cases, point a
manifest at local inputs and add `target_transcript` for offline/manual review,
or enable STT with `SARVAM_API_KEY`. Start the reviewer UI with:

```sh
python3 -m shorts_fidelity_judge.review_ui output/mat_armstrong_fixture/report.json
```
