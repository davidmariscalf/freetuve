import shutil
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .exercises import score_answer
from .models import AttemptRequest, LessonCreate
from .service import process_lesson
from .storage import create_pending_lesson, ensure_data_dirs, lesson_dir, load_lesson, save_lesson
from .transcription import transcription_available
from .youtube import validate_youtube_url


app = FastAPI(title="FreeTuve", version="0.2.0")
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
    if isinstance(result.get("transcription"), dict):
        result["transcription"].pop("caption_path", None)
    if result.get("status") == "ready":
        result["media_url"] = f"/api/lessons/{lesson['id']}/media"
        result["progress"] = _progress(lesson)
        for exercise in result.get("exercises", []):
            exercise.pop("expected", None)
            exercise.pop("transcript", None)
    return result


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "local_transcription": transcription_available(),
    }


@app.post("/api/lessons", status_code=202)
def create_lesson(payload: LessonCreate, background_tasks: BackgroundTasks) -> dict:
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=503, detail="FFmpeg no está instalado en el servidor")
    try:
        source_url = validate_youtube_url(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    lesson_id = str(uuid4())
    create_pending_lesson(
        lesson_id,
        source_url=source_url,
        language=payload.language,
        difficulty=payload.difficulty,
        max_items=payload.max_items,
    )
    background_tasks.add_task(process_lesson, lesson_id)
    return {"id": lesson_id, "status": "pending"}


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    return _public_lesson(_load_or_404(lesson_id))


@app.get("/api/lessons/{lesson_id}/media")
def get_media(lesson_id: str):
    lesson = _load_or_404(lesson_id)
    if lesson.get("status") != "ready" or not lesson.get("media_path"):
        raise HTTPException(status_code=409, detail="La lección todavía no está lista")
    path = Path(lesson["media_path"]).resolve()
    root = lesson_dir(lesson_id).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=403, detail="Ruta de vídeo no válida")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="El vídeo ya no está disponible")
    return FileResponse(path)


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
