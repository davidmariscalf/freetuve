# FreeTuve

FreeTuve turns a video from a supported public platform into an interactive language listening lesson. It prefers existing subtitles, falls back to local speech to text when needed, can download the processed video to the user's device, and can save compact audio exercises for offline study.

## FreeTuve 1.3

The complete learning flow is:

1. Paste an HTTPS URL for an individual video on a supported platform.
2. Choose language, difficulty and lesson length.
3. FreeTuve validates that the URL resolves to the public Internet and rejects private, local, credential-bearing or non-standard-port URLs.
4. `yt-dlp` selects the matching built-in extractor and rejects unsupported live, playlist or overlong sources before the main download.
5. `yt-dlp` obtains a browser-playable copy and FFmpeg merges streams when needed.
6. FreeTuve first tries subtitles supplied by the source platform.
7. If captions are missing or too sparse, `faster-whisper` transcribes speech locally and FreeTuve creates its own WebVTT file.
8. Captions are cleaned and grouped into useful short phrases.
9. Phrases become cloze, multiple choice or dictation exercises.
10. The learner listens at least twice before answering. Extra replays carry a small score penalty.
11. The full phrase is revealed after the answer and mistakes return later in the same session.
12. The processed video can be downloaded explicitly to the learner's device while its temporary server copy still exists.
13. A lesson can also be saved offline. FreeTuve stores only the exercise audio clips plus exercise data, not the entire video.
14. The web app is installable as a PWA and saved lessons remain available without a network connection.
15. Temporary server copies are removed automatically after the configured retention period or immediately when the user chooses to delete them.

No paid AI API is required.

## Platform support

FreeTuve uses `yt-dlp`, whose built-in extractors cover a large number of video services including major social and video platforms. Support is not literally universal: websites change, some require authentication or cookies, some block server traffic, and DRM-protected media is intentionally not bypassed.

For public deployments, FreeTuve disables yt-dlp's generic extractor by default and uses only its built-in site extractors. This avoids turning the server into a general-purpose outbound URL fetcher while still covering a broad set of known platforms.

Trusted self-hosted installations can opt into the generic extractor:

```text
FREETUVE_ALLOW_GENERIC_EXTRACTOR=1
```

Do not enable that option on an Internet-facing deployment unless outbound networking is isolated from private/internal services at the infrastructure level.

## Subtitle strategy

```text
source-platform subtitles
          ↓ missing or insufficient
   local faster-whisper
          ↓
   generated WebVTT
          ↓
cleanup and phrase segmentation
          ↓
 interactive exercises
```

Local transcription defaults to the multilingual `base` Whisper model on CPU using INT8. The model is downloaded on first use and cached under `data/models/`.

## Offline design

When a learner selects **Guardar offline**, the server extracts only the short audio spans used by the lesson. The browser stores those clips in Cache Storage and stores the lesson manifest locally. The installed PWA can then replay and score the saved exercises without contacting the server.

Downloading the processed video is a separate explicit action. It is never required for offline lessons.

Deleting a server lesson does not remove an already saved offline copy from the learner's device. Offline copies can be removed from the local library independently.

## Production defaults

```text
FREETUVE_LESSON_TTL_HOURS=24
FREETUVE_MAX_VIDEO_SECONDS=3600
FREETUVE_MAX_MEDIA_MB=250
FREETUVE_CREATE_LIMIT_PER_HOUR=10
FREETUVE_OFFLINE_AUDIO_KBPS=64
FREETUVE_ALLOW_GENERIC_EXTRACTOR=0
FREETUVE_WHISPER_MODEL=base
FREETUVE_WHISPER_DEVICE=cpu
FREETUVE_WHISPER_COMPUTE_TYPE=int8
FREETUVE_MODEL_DIR=/custom/model/cache
```

These values are configurable. The defaults mean temporary lesson files are retained for 24 hours, source videos are limited to 60 minutes and 250 MB, one client can create at most 10 lessons per hour per server process, and only known yt-dlp site extractors are enabled.

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

GitHub Actions runs on every push and pull request. It compiles Python, validates frontend JavaScript and the PWA manifest, runs unit tests, builds the production Docker image, starts the image and checks `/api/health` from the running container. Unit tests do not download a Whisper model.

## Architecture

```text
frontend/index.html     browser UI and download control
frontend/app.js         online and offline lesson player
frontend/sw.js          PWA shell and offline clip delivery
app/main.py             FastAPI routes, download endpoint, lifecycle and rate limiting
app/youtube.py          multiplatform URL safety, yt-dlp preflight and ingestion
app/transcription.py    faster-whisper speech to text and WebVTT creation
app/vtt.py              caption cleanup and phrase segmentation
app/exercises.py        exercise generation and scoring
app/offline.py          compact AAC offline lesson packs
app/service.py          processing pipeline and caption fallback selection
app/storage.py          persistence, retention cleanup and deletion
tests/                  regression tests
```

`app/youtube.py` keeps its historical filename for compatibility, but its implementation is now platform-agnostic.

## Privacy and storage

FreeTuve does not require accounts. Server lesson directories use random UUIDs. Internal paths, the original source URL and correct answers are not exposed by the normal lesson endpoint. Correct answers are included only in the explicitly requested offline pack so the device can score exercises without a server connection.

Temporary lesson data is deleted after the configured TTL. The user can also delete a lesson from the server immediately. Locally saved PWA data remains on that device until the learner deletes it or clears site data.

## Safety and usage

FreeTuve is a learning tool, not a DRM or access-control bypass service. Only process or download videos when you have permission or another lawful basis to do so, and follow the terms that apply to the source platform and content.

The public-server defaults accept only HTTPS public Internet URLs, reject local/private destinations, credentials, direct live streams, playlists and configured media-limit violations, and disable yt-dlp's generic extractor.

## Upstream components

The project integrates `yt-dlp`, FFmpeg and `faster-whisper` without copying their complete source trees into FreeTuve. Exact upstream references are recorded in `upstream.lock.json`; license notes are in `THIRD_PARTY.md`.
