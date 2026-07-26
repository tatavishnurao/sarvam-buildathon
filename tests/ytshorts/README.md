# YouTube Shorts test fixtures

Each Short gets one self-contained folder:

```text
tests/ytshorts/<case-id>/
├── case.json
├── source/
│   └── source.mp4
├── dubbed/
│   └── <language-code>.wav
└── artifacts/                 # generated; do not hand-edit
```

## Media policy

Add videos manually only when you own the content, have permission, or are using a private evaluation copy permitted by the platform and applicable law. The repository ignores common media files by default. Commit metadata, transcripts, evaluation labels, and synthetic fixtures—not third-party source media.

## Workflow

1. Place the local source video at `source/source.mp4`.
2. In Sarvam Creator Studio, create the dub and export the target-language WAV.
3. Place that WAV at `dubbed/<language-code>.wav`.
4. Copy `case.example.json` to `case.json` and edit the metadata.
5. Run:

```bash
dubpatch-ingest tests/ytshorts/<case-id>/case.json
```

The command extracts a 16 kHz mono WAV from the source video and runs **Saaras v3 Batch STT** on both source and target audio. Batch is required because Shorts can exceed the synchronous endpoint's 30-second limit and because diarisation/timestamps are needed for later alignment.
