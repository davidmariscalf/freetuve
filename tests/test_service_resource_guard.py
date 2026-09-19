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


def test_source_type_selects_the_correct_duration_limit(tmp_path, monkeypatch):
    captured = []

    def run_case(source_type, expected_limit):
        lesson = {
            "id": "00000000-0000-0000-0000-000000000001",
            "status": "pending",
            "source_url": "https://example.com/media",
            "language": "en",
            "difficulty": "medium",
            "max_items": 5,
            "source_type": source_type,
            "attempts": [],
        }

        monkeypatch.setattr(service, "load_lesson", lambda _lesson_id: lesson)
        monkeypatch.setattr(service, "save_lesson", lambda _data: None)
        monkeypatch.setattr(service, "lesson_dir", lambda _lesson_id: tmp_path)

        def capture_limit(*_args, **kwargs):
            captured.append(kwargs["max_duration_seconds"])
            raise RuntimeError("stop after duration capture")

        monkeypatch.setattr(service, "download_media_and_captions", capture_limit)
        service._process_lesson_locked(lesson["id"])
        assert captured[-1] == expected_limit

    run_case("video", service.MAX_VIDEO_DURATION_SECONDS)
    run_case("movie", service.MAX_MOVIE_DURATION_SECONDS)
