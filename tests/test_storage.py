from datetime import datetime, timedelta, timezone
from uuid import uuid4

import app.storage as storage


def test_cleanup_removes_only_expired_lessons(tmp_path, monkeypatch):
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(storage, "LESSONS_ROOT", lessons)
    lessons.mkdir()

    fresh_id = str(uuid4())
    old_id = str(uuid4())
    storage.save_lesson({"id": fresh_id, "status": "ready"})
    storage.save_lesson({"id": old_id, "status": "ready"})

    old = storage.load_lesson(old_id)
    old["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    target = storage.lesson_file(old_id)
    target.write_text(__import__("json").dumps(old), encoding="utf-8")

    assert storage.cleanup_expired_lessons(24) == 1
    assert storage.lesson_file(fresh_id).exists()
    assert not storage.lesson_dir(old_id).exists()


def test_delete_lesson_is_idempotent_at_storage_layer(tmp_path, monkeypatch):
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(storage, "LESSONS_ROOT", lessons)
    lessons.mkdir()
    lesson_id = str(uuid4())
    storage.save_lesson({"id": lesson_id, "status": "ready"})
    assert storage.delete_lesson(lesson_id) is True
    assert storage.delete_lesson(lesson_id) is False
