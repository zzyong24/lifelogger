# Quality Guidelines

> Code quality standards for lifelogger.

---

## Lazy Loading Rule

All heavy models (Whisper, pyannote, SpeechBrain) MUST be lazy-loaded — only instantiated on first use.

```python
# ✅ Correct — lazy load
def _get_model(self):
    if self._model is None:
        from faster_whisper import WhisperModel
        self._model = WhisperModel(...)
    return self._model

# ❌ Wrong — load at import time
from faster_whisper import WhisperModel
model = WhisperModel(...)  # blocks startup, wastes memory if unused
```

---

## Config Access

Always load config through `load_config()` in `pipeline/daily_pipeline.py`.
Never hardcode paths or thresholds.

```python
# ✅ Correct
cfg = load_config()
threshold = cfg["diarization"]["speaker_match_threshold"]

# ❌ Wrong
threshold = 0.82  # magic number
```

---

## Secrets

- HF token: `config/settings.local.yaml` → `diarization.hf_token` OR env var `HF_TOKEN`
- Never commit `settings.local.yaml`
- Never hardcode tokens in source

---

## Error Handling in Pipeline

Pipeline steps must NOT crash the whole run on single file failure.
Wrap per-file processing in try/except and log warnings.

```python
# ✅ Correct
for audio_file in active_files:
    try:
        result = transcriber.transcribe(audio_file)
    except Exception as e:
        logger.error(f"转写失败 ({audio_file.name}): {e}")
        continue  # skip, don't crash
```

---

## Logging

Use `logging.getLogger(__name__)` in every module.
Never use `print()` in library code — only in `main.py` CLI layer via `rich`.

---

## Forbidden Patterns

```python
# ❌ Hardcoded paths
Path.home() / "Library/Application Support/lifelogger"

# ❌ Import-time model loading
import pyannote; pipeline = Pipeline.from_pretrained(...)

# ❌ print() in modules
print(f"Processing {file}")  # use logger.info() instead

# ❌ Secrets in code
hf_token = "hf_xxxxxxxxxxxx"
```
