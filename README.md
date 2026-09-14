# FreeTuve

FreeTuve converts a YouTube video into an interactive language listening lesson.

## What it does

1. Paste a YouTube URL.
2. Choose the subtitle language and difficulty.
3. FreeTuve downloads a browser playable copy of the video with `yt-dlp` and uses FFmpeg when streams need merging.
4. It retrieves manual or automatic WebVTT subtitles, removes caption noise and groups them into useful short phrases.
5. Each phrase becomes a listening exercise: cloze, multiple choice or dictation depending on difficulty.
6. The learner must listen at least twice before answering. Extra replays are allowed with a small score penalty.
7. Wrong answers are scheduled again later in the same lesson.
8. Progress and attempts are stored locally in `data/`.

The exercise generator is deterministic and does not require an AI API or paid service.

## Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`.

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

CI also compiles the Python package before running tests.

## Current product scope

The finished MVP supports YouTube, six language choices in the UI, difficulty levels from easy to expert, up to 40 exercises per lesson, local progress, replay speed controls and adaptive review of mistakes.

A video needs usable YouTube subtitles in the selected language. Local speech to text is intentionally not bundled yet because shipping a large transcription model would make the first deployment substantially heavier and slower. This is the main functional limitation of the MVP.

## Architecture

```text
frontend/          browser UI and lesson player
app/main.py        FastAPI routes
app/youtube.py     YouTube validation and yt-dlp ingestion
app/vtt.py         WebVTT cleanup and phrase segmentation
app/exercises.py   exercise generation and scoring
app/service.py     processing pipeline
app/storage.py     local persistent lesson storage
tests/             unit tests
```

## Safety and usage

FreeTuve is a learning tool, not a copyright bypass service. Only download or process videos when you have permission or another lawful basis to do so, and follow the terms that apply to the source platform and content.

The server deliberately accepts only HTTPS YouTube hosts rather than arbitrary URLs.

## Upstream components

The project integrates `yt-dlp` and FFmpeg without copying their full repositories into FreeTuve. Exact upstream references are recorded in `upstream.lock.json`; license notes are in `THIRD_PARTY.md`.
