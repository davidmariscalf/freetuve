# FreeTuve

FreeTuve converts a YouTube video into an interactive language listening lesson.

## What it does

1. Paste a YouTube URL.
2. Choose the language and difficulty.
3. FreeTuve downloads a browser playable copy of the video with `yt-dlp` and uses FFmpeg when streams need merging.
4. It first tries manual or automatic YouTube WebVTT subtitles.
5. If usable subtitles are missing or too sparse, FreeTuve automatically transcribes the video's speech locally with `faster-whisper` and creates its own WebVTT subtitles.
6. Subtitle cues are cleaned and grouped into useful short phrases.
7. Each phrase becomes a listening exercise: cloze, multiple choice or dictation depending on difficulty.
8. The learner must listen at least twice before answering. Extra replays are allowed with a small score penalty.
9. After answering, the complete subtitle is revealed below the video so the learner can compare what they heard with the actual phrase.
10. Wrong answers are scheduled again later in the same lesson.
11. Progress and attempts are stored locally in `data/`.

The exercise generator and speech-to-text pipeline do not require an AI API or paid service.

## Subtitle strategy

FreeTuve uses this order:

```text
YouTube manual/automatic subtitles
          ↓ missing or unusable
local faster-whisper transcription
          ↓
WebVTT cleanup and phrase segmentation
          ↓
interactive exercises
```

Local transcription defaults to the multilingual `small` Whisper model on CPU using INT8. The model is downloaded on first use and cached under `data/models/` when using the default configuration.

Environment variables:

```text
FREETUVE_WHISPER_MODEL=small
FREETUVE_WHISPER_DEVICE=cpu
FREETUVE_WHISPER_COMPUTE_TYPE=int8
FREETUVE_MODEL_DIR=/custom/model/cache
```

For a CUDA deployment, set the device and an appropriate compute type for the installed environment.

## Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`.

The first lesson that needs local transcription may take longer because the speech model has to be downloaded once. The `data/` volume also keeps the model cache between container restarts.

## Run locally

Requirements: Python 3.12+, Git and FFmpeg available on `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

CI compiles the Python package, checks frontend JavaScript syntax and runs the unit tests. Tests do not download a Whisper model.

## Product scope

The MVP supports YouTube, six language choices in the UI, difficulty levels from easy to expert, up to 40 exercises per lesson, local progress, replay speed controls, adaptive review of mistakes and local speech-to-text fallback.

The main remaining operational limitation is compute: local transcription is substantially heavier than consuming existing subtitles, especially on CPU and for long videos. YouTube availability, geographic restrictions and source-platform changes can also affect ingestion.

## Architecture

```text
frontend/              browser UI and lesson player
app/main.py            FastAPI routes
app/youtube.py         YouTube validation and yt-dlp ingestion
app/transcription.py   faster-whisper local speech-to-text and WebVTT creation
app/vtt.py             WebVTT cleanup and phrase segmentation
app/exercises.py       exercise generation and scoring
app/service.py         processing pipeline and caption fallback selection
app/storage.py         local persistent lesson storage
tests/                 unit tests
```

## Safety and usage

FreeTuve is a learning tool, not a copyright bypass service. Only download or process videos when you have permission or another lawful basis to do so, and follow the terms that apply to the source platform and content.

The server deliberately accepts only HTTPS YouTube hosts rather than arbitrary URLs.

## Upstream components

The project integrates `yt-dlp`, FFmpeg and `faster-whisper` without copying their full repositories into FreeTuve. Exact upstream references are recorded in `upstream.lock.json`; license notes are in `THIRD_PARTY.md`.
