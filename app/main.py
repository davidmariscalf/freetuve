import asyncio
import ipaddress
import re
import shutil
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    ALLOW_GENERIC_EXTRACTOR,
    ALLOWED_ORIGINS,
    APP_VERSION,
    CLEANUP_INTERVAL_SECONDS,
    CREATE_LIMIT_PER_HOUR,
    LESSON_TTL_HOURS,
    MAX_VIDEO_DURATION_SECONDS,
)
from .exercises import score_answer
from .models import AttemptRequest, LessonCreate
from .offline import build_offline_pack, offline_clip_path
from .service import process_lesson
from .storage import (
    cleanup_expired_lessons,
    create_pending_lesson,
    delete_lesson,
    ensure_data_dirs,
    lesson_dir,
    load_lesson,
    recoverable_lesson_ids,
    save_lesson,
)
from .transcription import transcription_available
from .youtube import validate_source_url


_CREATE_EVENTS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = threading.Lock()
_RECOVERY_TASKS: set[asyncio.Task] = set()


def _client_rate_key(request: Request) -> str:
    # Railway's public proxy supplies X-Real-IP for the original remote client.
    # Only trust that header when the immediate socket peer is non-public; a
    # direct public client can otherwise spoof X-Real-IP and rotate rate-limit
    # buckets at will.
    peer = request.client.host if request.client else "unknown"
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        try:
            peer_ip = ipaddress.ip_address(peer)
            forwarded_ip = ipaddress.ip_address(real_ip)
        except ValueError:
            pass
        else:
            if not peer_ip.is_global:
                return str(forwarded_ip)
    return peer


def _check_create_limit(client: str) -> None:
    now = time.monotonic()
    cutoff = now - 3600
    with _RATE_LOCK:
        bucket = _CREATE_EVENTS[client]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= CREATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail="Has creado demasiadas lecciones en la última hora. Inténtalo más tarde.",
            )
        bucket.append(now)


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        await asyncio.to_thread(cleanup_expired_lessons, LESSON_TTL_HOURS)


def _track_recovery_task(task: asyncio.Task) -> None:
    _RECOVERY_TASKS.add(task)
    task.add_done_callback(_RECOVERY_TASKS.discard)


def _resume_interrupted_lessons() -> int:
    lesson_ids = recoverable_lesson_ids()
    for lesson_id in lesson_ids:
        task = asyncio.create_task(
            asyncio.to_thread(process_lesson, lesson_id),
            name=f"recover-lesson-{lesson_id}",
        )
        _track_recovery_task(task)
    return len(lesson_ids)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_data_dirs()
    await asyncio.to_thread(cleanup_expired_lessons, LESSON_TTL_HOURS)
    _resume_interrupted_lessons()
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        for task in list(_RECOVERY_TASKS):
            task.cancel()
        if _RECOVERY_TASKS:
            await asyncio.gather(*list(_RECOVERY_TASKS), return_exceptions=True)


app = FastAPI(title="FreeTuve", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
ensure_data_dirs()


def _load_or_404(lesson_id: str) -> dict:
    try:
        return load_lesson(lesson_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Lección no encontrada") from None


def _progress(lesson: dict) -> dict:
    attempts = lesson.get("attempts", [])
    unique = {item["exercise_id"] for item in attempts}
    correct = sum(1 for item in attempts if item.get("correct"))
    return {
        "attempts": len(attempts),
        "unique_exercises_attempted": len(unique),
        "correct_attempts": correct,
        "average_score": round(sum(item.get("score", 0) for item in attempts) / len(attempts), 1) if attempts else 0,
    }


def _public_lesson(lesson: dict) -> dict:
    result = deepcopy(lesson)
    result.pop("media_path", None)
    result.pop("caption_path", None)
    result.pop("attempts", None)
    result.pop("manual_transcript", None)
    if isinstance(result.get("transcription"), dict):
        result["transcription"].pop("caption_path", None)
    result["retention_hours"] = LESSON_TTL_HOURS
    if result.get("status") == "ready":
        result["media_url"] = f"/api/lessons/{lesson['id']}/media"
        result["download_url"] = f"/api/lessons/{lesson['id']}/download"
        result["progress"] = _progress(lesson)
        for exercise in result.get("exercises", []):
            exercise.pop("expected", None)
            exercise.pop("transcript", None)
    return result


def _media_path(lesson: dict) -> Path:
    if lesson.get("status") != "ready" or not lesson.get("media_path"):
        raise HTTPException(status_code=409, detail="La lección todavía no está lista")
    path = Path(lesson["media_path"]).resolve()
    root = lesson_dir(lesson["id"]).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=403, detail="Ruta de vídeo no válida")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="El vídeo ya no está disponible")
    return path


def _download_filename(lesson: dict, path: Path) -> str:
    title = str(lesson.get("title") or "freetuve-video")
    safe = re.sub(r"[^\w .()-]+", "_", title, flags=re.UNICODE).strip(" ._")
    safe = safe[:120] or "freetuve-video"
    return f"{safe}{path.suffix.casefold()}"


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": APP_VERSION,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "local_transcription": transcription_available(),
        "lesson_ttl_hours": LESSON_TTL_HOURS,
        "max_video_minutes": MAX_VIDEO_DURATION_SECONDS // 60,
        "multiplatform": True,
        "generic_extractor": ALLOW_GENERIC_EXTRACTOR,
        "crash_recovery": True,
        "recovering_lessons": len(_RECOVERY_TASKS),
    }


@app.post("/api/lessons", status_code=202)
def create_lesson(payload: LessonCreate, background_tasks: BackgroundTasks, request: Request) -> dict:
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=503, detail="FFmpeg no está instalado en el servidor")
    _check_create_limit(_client_rate_key(request))
    try:
        source_url = validate_source_url(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    lesson_id = str(uuid4())
    create_pending_lesson(
        lesson_id,
        source_url=source_url,
        language=payload.language,
        difficulty=payload.difficulty,
        max_items=payload.max_items,
        manual_transcript=payload.manual_transcript,
    )
    background_tasks.add_task(process_lesson, lesson_id)
    return {"id": lesson_id, "status": "pending", "retention_hours": LESSON_TTL_HOURS}


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    return _public_lesson(_load_or_404(lesson_id))


@app.delete("/api/lessons/{lesson_id}", status_code=204)
def remove_lesson(lesson_id: str):
    try:
        removed = delete_lesson(lesson_id)
    except ValueError:
        removed = False
    if not removed:
        raise HTTPException(status_code=404, detail="Lección no encontrada")
    return None


@app.get("/api/lessons/{lesson_id}/media")
def get_media(lesson_id: str):
    lesson = _load_or_404(lesson_id)
    path = _media_path(lesson)
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/lessons/{lesson_id}/download")
def download_media(lesson_id: str):
    lesson = _load_or_404(lesson_id)
    path = _media_path(lesson)
    return FileResponse(
        path,
        filename=_download_filename(lesson, path),
        headers={"Cache-Control": "private, no-store"},
    )


@app.post("/api/lessons/{lesson_id}/offline-pack")
def create_offline_pack(lesson_id: str) -> dict:
    lesson = _load_or_404(lesson_id)
    try:
        return build_offline_pack(lesson)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/lessons/{lesson_id}/offline/{filename}")
def get_offline_clip(lesson_id: str, filename: str):
    _load_or_404(lesson_id)
    try:
        path = offline_clip_path(lesson_id, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Fragmento offline no encontrado")
    return FileResponse(
        path,
        media_type="audio/mp4",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@app.post("/api/lessons/{lesson_id}/attempts")
def submit_attempt(lesson_id: str, payload: AttemptRequest) -> dict:
    lesson = _load_or_404(lesson_id)
    if lesson.get("status") != "ready":
        raise HTTPException(status_code=409, detail="La lección todavía no está lista")

    exercise = next((item for item in lesson.get("exercises", []) if item["id"] == payload.exercise_id), None)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    if payload.listens < exercise.get("min_listens", 2):
        raise HTTPException(status_code=400, detail="Escucha el fragmento al menos dos veces antes de responder")

    result = score_answer(exercise, payload.answer, payload.listens)
    lesson.setdefault("attempts", []).append({
        "exercise_id": payload.exercise_id,
        "listens": payload.listens,
        "correct": result["correct"],
        "accuracy": result["accuracy"],
        "score": result["score"],
    })
    save_lesson(lesson)
    result["progress"] = _progress(lesson)
    return result


frontend = Path(__file__).resolve().parent.parent / "frontend"
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
