from app.service import _discard_sensitive_inputs


def test_terminal_state_discards_sensitive_inputs():
    lesson = {
        "id": "lesson",
        "status": "ready",
        "source_url": "https://example.com/video?token=secret",
        "manual_transcript": "private transcript",
        "title": "Safe metadata",
    }

    _discard_sensitive_inputs(lesson)

    assert "source_url" not in lesson
    assert "manual_transcript" not in lesson
    assert lesson["title"] == "Safe metadata"
