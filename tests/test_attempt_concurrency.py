from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import app.storage as storage
from app.main import submit_attempt
from app.models import AttemptRequest


def test_concurrent_attempt_submissions_do_not_lose_progress(tmp_path, monkeypatch):
    lessons = tmp_path / "lessons"
    deleted = tmp_path / "deleted"
    monkeypatch.setattr(storage, "LESSONS_ROOT", lessons)
    monkeypatch.setattr(storage, "DELETED_ROOT", deleted)
    storage.ensure_data_dirs()

    lesson_id = str(uuid4())
    storage.save_lesson({
        "id": lesson_id,
        "status": "ready",
        "attempts": [],
        "exercises": [{
            "id": "ex-1",
            "type": "cloze",
            "expected": ["world"],
            "transcript": "Hello world",
            "min_listens": 2,
        }],
    })
    payload = AttemptRequest(exercise_id="ex-1", answer=["world"], listens=2)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: submit_attempt(lesson_id, payload), range(24)))

    saved = storage.load_lesson(lesson_id)
    assert len(results) == 24
    assert len(saved["attempts"]) == 24
    assert saved["attempts"][-1]["correct"] is True
