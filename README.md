# FreeTuve

FreeTuve turns a YouTube video into an interactive language listening lesson. It prefers existing subtitles, falls back to local speech to text when needed, and can save compact audio exercises on the learner's device for offline study.

## FreeTuve 1.0

The complete learning flow is:

1. Paste a YouTube URL.
2. Choose language, difficulty and lesson length.
3. FreeTuve validates the source and rejects unsupported live or overlong videos before the main download.
4. `yt-dlp` obtains a browser playable copy and FFmpeg merges streams when needed.
5. FreeTuve first tries manual or automatic YouTube WebVTT subtitles.
6. If captions are missing or too sparse, `faster-whisper` transcribes speech locally and FreeTuve creates its own WebVTT file.
7. Captions are cleaned and grouped into useful short phrases.
8. Phrases become cloze, multiple choice or dictation exercises.
9. The learner listens at least twice before answering. Extra replays carry a small score penalty.
10. The full phrase is revealed after the answer and mistakes return later in the same session.
11. A lesson can be saved offline. FreeTuve stores only the exercise audio clips plus exercise data, not the entire video.
12. The web app is installable as a PWA and saved lessons remain available without a network connection.
13. Temporary server copies are removed automatically after the configured retention period or immediately when the user chooses to delete them.

No paid AI API is required.

## Subtitle strategy

```text
YouTube manual or automatic subtitles
                ↓ missing or insufficient
        local faster-whisper
                ↓
       generated WebVTT
                ↓
 cleanup and phrase segmentation
                ↓
      interactive exercises
```

Local transcription defaults to the multilingual `small` Whisper model on CPU using INT8. The model is downloaded on first use and cached under `data/models/`.

## Offline design

Offline mode deliberately does not turn FreeTuve into a full video downloader. When a learner selects **Guardar offline**, the server extracts only the short audio spans used by the lesson. The browser stores those clips in Cache Storage and stores the lesson manifest locally. The installed PWA can then replay and score the saved exercises without contacting the server.

Deleting a server lesson does not remove an already saved offline copy from the learner's device. Offline copies can be removed from the local library independently.

## Production defaults

```text
FREETUVE_LESSON_TTL_HOURS=24
FREETUVE_MAX_VIDEO_SECONDS=3600
FREETUVE_MAX_MEDIA_MB=750
FREETUVE_CREATE_LIMIT_PER_HOUR=10
FREETUVE_OFFLINE_AUDIO_KBPS=64
FREETUVE_WHISPER_MODEL=small
FREETUVE_WHISPER_DEVICE=cpu
FREETUVE_WHISPER_COMPUTE_TYPE=int8
FREETUVE_MODEL_DIR=/custom/model/cache
```

These values are configurable. The defaults mean temporary lesson files are retained for 24 hours, source videos are limited to 60 minutes and 750 MB, and one client can create at most 10 lessons per hour per server process.

## Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`.

The first lesson that needs local transcription may take longer because the speech model must be downloaded once. The `data/` volume persists the model cache and temporary lesson data between container restarts.

For public deployment, use HTTPS. Service workers and installable PWA behavior require a secure context outside localhost.

## Run locally

Requirements: Python 3.12+, Git and FFmpeg available on `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Tests and CI

```bash
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions runs on every push and pull request. It compiles Python, validates both frontend JavaScript files and the PWA manifest, runs unit tests, builds the production Docker image, starts the image and checks `/api/health` from the running container. Unit tests do not download a Whisper model.

## Architecture

```text
frontend/index.html     browser UI
frontend/app.js         online and offline lesson player
frontend/sw.js          PWA shell and offline clip delivery
app/main.py             FastAPI routes, lifecycle and rate limiting
app/youtube.py          YouTube preflight and yt-dlp ingestion
app/transcription.py    faster-whisper speech to text and WebVTT creation
app/vtt.py              caption cleanup and phrase segmentation
app/exercises.py        exercise generation and scoring
app/offline.py          compact AAC offline lesson packs
app/service.py          processing pipeline and caption fallback selection
app/storage.py          persistence, retention cleanup and deletion
tests/                  regression tests
```

## Privacy and storage

FreeTuve does not require accounts. Server lesson directories use random UUIDs. Internal paths and correct answers are not exposed by the normal lesson endpoint. Correct answers are included only in the explicitly requested offline pack so the device can score exercises without a server connection.

Temporary lesson data is deleted after the configured TTL. The user can also delete a lesson from the server immediately. Locally saved PWA data remains on that device until the learner deletes it or clears site data.

## Safety and usage

FreeTuve is a learning tool, not a copyright bypass service. Only process videos when you have permission or another lawful basis to do so, and follow the terms that apply to the source platform and content.

The server accepts only HTTPS YouTube hosts, rejects live streams, enforces configurable media limits and does not act as a general purpose URL fetcher.

## Upstream components

The project integrates `yt-dlp`, FFmpeg and `faster-whisper` without copying their complete source trees into FreeTuve. Exact upstream references are recorded in `upstream.lock.json`; license notes are in `THIRD_PARTY.md`.
