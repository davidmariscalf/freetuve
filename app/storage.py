import json
import os
from pathlib import Path
from uuid import UUID


DATA_ROOT = Path(os.getenv("FREETUVE_DATA_DIR", "data")).resolve()
LESSONS_ROOT = DATA_ROOT / "lessons"


def ensure_data_dirs() -> None:
    LESSONS_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_lesson_id(lesson_id: str) -> str:
    return str(UUID(lesson_id))


def lesson_dir(lesson_id: str, *, create: bool = False) -> Path:
    safe = _safe_lesson_id(lesson_id)
    path = (LESSONS_ROOT / safe).resolve()
    if LESSONS_ROOT not in path.parents:
        raise ValueError("Invalid lesson id")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def lesson_file(lesson_id: str) -> Path:
    return lesson_dir(lesson_id) / "lesson.json"


def save_lesson(data: dict) -> None:
    ensure_data_dirs()
    directory = lesson_dir(data["id"], create=True)
    target = directory / "lesson.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def load_lesson(lesson_id: str) -> dict:
    target = lesson_file(lesson_id)
    if not target.exists():
        raise FileNotFoundError(lesson_id)
    return json.loads(target.read_text(encoding="utf-8"))


def create_pending_lesson(lesson_id: str, *, source_url: str, language: str, difficulty: str, max_items: int) -> dict:
    data = {
        "id": lesson_id,
        "status": "pending",
        "source_url": source_url,
        "language": language,
        "difficulty": difficulty,
        "max_items": max_items,
        "attempts": [],
    }
    save_lesson(data)
    return data
