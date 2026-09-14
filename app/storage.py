import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID


DATA_ROOT = Path(os.getenv("FREETUVE_DATA_DIR", "data")).resolve()
LESSONS_ROOT = DATA_ROOT / "lessons"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


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
    now = _iso_now()
    data.setdefault("created_at", now)
    data["updated_at"] = now
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def load_lesson(lesson_id: str) -> dict:
    target = lesson_file(lesson_id)
    if not target.exists():
        raise FileNotFoundError(lesson_id)
    return json.loads(target.read_text(encoding="utf-8"))


def delete_lesson(lesson_id: str) -> bool:
    directory = lesson_dir(lesson_id)
    if not directory.exists():
        return False
    shutil.rmtree(directory)
    return True


def cleanup_expired_lessons(ttl_hours: int) -> int:
    ensure_data_dirs()
    cutoff = _now() - timedelta(hours=max(1, ttl_hours))
    removed = 0
    for directory in LESSONS_ROOT.iterdir():
        if not directory.is_dir():
            continue
        metadata = directory / "lesson.json"
        timestamp = None
        if metadata.exists():
            try:
                data = json.loads(metadata.read_text(encoding="utf-8"))
                raw = data.get("updated_at") or data.get("created_at")
                if raw:
                    timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                timestamp = None
        if timestamp is None:
            timestamp = datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
        if timestamp < cutoff:
            shutil.rmtree(directory, ignore_errors=True)
            removed += 1
    return removed


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
