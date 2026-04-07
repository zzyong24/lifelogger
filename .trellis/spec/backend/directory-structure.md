# Directory Structure

> How lifelogger code is organized.

---

## Overview

lifelogger is a Python pipeline project with clear module separation. Each directory owns one responsibility.

---

## Directory Layout

```
lifelogger/
├── main.py                    # CLI entry point (click)
├── requirements.txt
├── pyproject.toml
│
├── config/
│   ├── settings.yaml          # Default config (committed)
│   └── settings.local.yaml   # Local overrides (gitignored, private)
│
├── recorder/                  # Audio capture module
│   └── audio_recorder.py     # AudioRecorder class
│
├── diarizer/                  # Speaker diarization module
│   └── speaker_diarizer.py   # SpeakerDiarizer + SpeakerSegment
│
├── transcriber/               # Whisper transcription module
│   └── whisper_transcriber.py # WhisperTranscriber + TranscriptResult
│
├── vault/                     # Vault output module
│   └── markdown_writer.py    # VaultWriter + segments_to_markdown()
│
├── pipeline/                  # Orchestration
│   ├── daily_pipeline.py     # run_pipeline() — main daily job
│   └── silence_filter.py     # has_speech() + filter_recordings()
│
├── speakers/                  # Speaker embeddings (.npy files, gitignored)
│
└── scripts/
    ├── install.sh             # One-click install
    └── com.lifelogger.recorder.plist  # macOS launchd autostart
```

---

## Module Responsibilities

| Module | Responsibility | Key Class |
|--------|---------------|-----------|
| `recorder` | Capture audio from BlackHole/mic | `AudioRecorder` |
| `diarizer` | Separate speakers + identify names | `SpeakerDiarizer` |
| `transcriber` | Whisper transcription, align with speakers | `WhisperTranscriber` |
| `vault` | Convert to Markdown, write to Vault | `VaultWriter` |
| `pipeline` | Orchestrate the daily job | `run_pipeline()` |

---

## Naming Conventions

- Python files: `snake_case.py`
- Classes: `PascalCase` (e.g., `AudioRecorder`, `SpeakerDiarizer`)
- Config keys: `snake_case`
- Speaker embedding files: `{name}.npy` under `speakers/`
- Recording files: `YYYYMMDD_HHMMSS.mp3`
- Vault output: `YYYY-MM-DD_lifelogs.md`

---

## Config Strategy

`settings.yaml` (committed) contains safe defaults.
`settings.local.yaml` (gitignored) contains secrets and machine-specific paths.

The pipeline always merges both with `settings.local.yaml` taking priority.
Never commit `settings.local.yaml`.
