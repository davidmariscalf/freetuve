import app.service as service


def test_repeated_resource_crash_marks_lesson_error(monkeypatch):
    lesson = {
        "id": "lesson-id",
        "status": "processing",
        "processing_attempts": service.MAX_PROCESSING_ATTEMPTS,
    }
    saved = []

    monkeypatch.setattr(service, "load_lesson", lambda _lesson_id: lesson)
    monkeypatch.setattr(service, "save_lesson", lambda data: saved.append(dict(data)))

    def should_not_download(*_args, **_kwargs):
        raise AssertionError("resource-exhausted lesson must not be processed again")

    monkeypatch.setattr(service, "download_media_and_captions", should_not_download)

    service._process_lesson_locked("lesson-id")

    assert lesson["status"] == "error"
    assert lesson["processing_attempts"] == service.MAX_PROCESSING_ATTEMPTS + 1
    assert "agotó repetidamente los recursos" in lesson["error"]
    assert saved[-1]["status"] == "error"
