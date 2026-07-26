Overview of this product/project:

<img width="931" height="1314" alt="image" src="https://github.com/user-attachments/assets/bf26c355-88b8-4973-b3d1-5d557bfc400c" />

## DubPatch

Evidence-first review for Sarvam-dubbed automotive Shorts. It produces
`preserved`, `review_required`, or `unable_to_verify`; it never emits a universal
accuracy score or autonomous certification.

## Milestone 1: ingest one real Short

The repository now supports this artifact flow:

```text
local creator-authorised source video
  -> ffmpeg extracts 16 kHz mono audio
  -> Saaras v3 Batch STT creates English transcript + speakers + timestamps

manually exported Sarvam Creator Studio dubbed WAV
  -> Saaras v3 Batch STT creates target-language transcript + speakers + timestamps

both results
  -> tests/ytshorts/<case>/artifacts/
```

Sarvam's beta API page currently lists no available beta endpoints. Creator
Studio dubbing is therefore a manual step for this milestone; the documented
Saaras v3 Batch API is used programmatically for both transcripts.

## Setup

Requirements:

- Python 3.11+
- `ffmpeg` and `ffprobe`
- Sarvam API key from `platform.sarvam.ai`

```sh
python3 -m venv sarvamgg
source sarvamgg/bin/activate
python -m pip install --upgrade pip
pip install -e .
export SARVAM_API_KEY="YOUR_KEY"
```

For the local React-to-Python review path, place the key in the ignored root
`.env` instead of exporting it, then run the API and frontend in separate
terminals:

```sh
source sarvamgg/bin/activate
dubpatch-api
```

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, confirm creator authorisation, and upload a local
source MP4 plus a manually exported Sarvam-dubbed WAV or MP4. URL ingest records
and normalizes a YouTube ID but does not download media; the upload remains the
reliable path. Runtime job state, media, raw provider caches, normalized
transcripts, alignments, reports, and reviewer corrections are stored under the
ignored `.runtime/jobs/` directory.

## Add the Mat Armstrong smoke test

```sh
mkdir -p tests/ytshorts/mat-armstrong-gallardo/{source,dubbed}
cp tests/ytshorts/mat-armstrong-gallardo/case.example.json \
   tests/ytshorts/mat-armstrong-gallardo/case.json
```

Then place these local files:

```text
tests/ytshorts/mat-armstrong-gallardo/source/source.mp4
tests/ytshorts/mat-armstrong-gallardo/dubbed/te-IN.wav
```

Run:

```sh
dubpatch-ingest tests/ytshorts/mat-armstrong-gallardo/case.json
```

Generated outputs:

```text
artifacts/source_audio.wav
artifacts/source_transcript.json
artifacts/target_transcript.json
artifacts/manifest.json
artifacts/raw/sarvam-stt/*.json
```

Media and generated artifacts are ignored by Git. Only commit metadata,
transcripts or labels that you are permitted to publish.

## Existing offline fixture

Run the fully offline synthetic acceptance-shaped fixture with:

```sh
./scripts/run_mat_armstrong_fixture.sh
python3 -m unittest discover -s tests -v
```

Results are written to `output/mat_armstrong_fixture/`. The fixture is not a
real Mat Armstrong transcript or Telugu dub; see its notice before replacing it
with supplied local source transcript and WAV files. Start the reviewer UI with:

```sh
python3 -m shorts_fidelity_judge.review_ui output/mat_armstrong_fixture/report.json
```
