from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import app.storage as storage


def set_roots(tmp_path, monkeypatch):
    lessons = tmp_path / "lessons"
    deleted = tmp_path / "deleted"
    monkeypatch.setattr(storage, "LESSONS_ROOT", lessons)
    monkeypatch.setattr(storage, "DELETED_ROOT", deleted)
    storage.ensure_data_dirs()
    return lessons, deleted


def test_cleanup_removes_only_expired_lessons(tmp_path, monkeypatch):
    set_roots(tmp_path, monkeypatch)
    fresh_id = str(uuid4())
    old_id = str(uuid4())
    storage.save_lesson({"id": fresh_id, "status": "ready"})
    storage.save_lesson({"id": old_id, "status": "processing"})

    old = storage.load_lesson(old_id)
    old["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    target = storage.lesson_file(old_id)
    target.write_text(__import__("json").dumps(old), encoding="utf-8")

    assert storage.cleanup_expired_lessons(24) == 1
    assert storage.lesson_file(fresh_id).exists()
    assert not storage.lesson_dir(old_id).exists()
    with pytest.raises(FileNotFoundError):
        storage.save_lesson({"id": old_id, "status": "ready"})


def test_delete_prevents_worker_from_recreating_lesson(tmp_path, monkeypatch):
    set_roots(tmp_path, monkeypatch)
    lesson_id = str(uuid4())
    storage.save_lesson({"id": lesson_id, "status": "processing"})
    assert storage.delete_lesson(lesson_id) is True
    assert storage.delete_lesson(lesson_id) is False

    with pytest.raises(FileNotFoundError):
        storage.save_lesson({"id": lesson_id, "status": "ready"})
    with pytest.raises(FileNotFoundError):
        storage.load_lesson(lesson_id)
    assert not storage.lesson_dir(lesson_id).exists()


def test_recoverable_lessons_only_returns_interrupted_work(tmp_path, monkeypatch):
    set_roots(tmp_path, monkeypatch)
    pending_id = str(uuid4())
    processing_id = str(uuid4())
    ready_id = str(uuid4())
    error_id = str(uuid4())
    deleted_id = str(uuid4())

    storage.save_lesson({"id": pending_id, "status": "pending"})
    storage.save_lesson({"id": processing_id, "status": "processing"})
    storage.save_lesson({"id": ready_id, "status": "ready"})
    storage.save_lesson({"id": error_id, "status": "error"})
    storage.save_lesson({"id": deleted_id, "status": "processing"})
    assert storage.delete_lesson(deleted_id) is True

    assert storage.recoverable_lesson_ids() == sorted([pending_id, processing_id])
