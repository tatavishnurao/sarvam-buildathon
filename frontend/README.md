# DubPatch frontend prototype

A polished, frontend-only Vite + React prototype for a Sarvam-powered authenticity review workflow for Indic-dubbed short-form video.

## Run

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Current scope

- Creator-authorised YouTube Short URL input
- Target-language selection
- Source/dubbed artifact workspace
- Mock Sarvam processing flow
- Fidelity findings for the Mat Armstrong Telugu test case
- Human-review and patch interactions as UI states

No live YouTube download, Sarvam API, transcription, judging or FFmpeg patching is implemented yet.

## Backend contracts to add next

- `POST /api/projects` — create review project from authorised URL or upload
- `POST /api/projects/:id/source` — ingest source video and transcript
- `POST /api/projects/:id/dub` — submit target language and start Sarvam dubbing
- `GET /api/projects/:id/artifacts` — source/dubbed transcripts, WAV and timing blocks
- `POST /api/projects/:id/judge` — generate evidence-backed fidelity report
- `POST /api/projects/:id/issues/:issueId/patch` — human-approved block regeneration

For public deployment, do not implement arbitrary YouTube downloading. Prefer creator uploads, creator-authorised URLs, or official platform access.
