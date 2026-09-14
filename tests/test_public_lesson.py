from pathlib import Path

from app.main import _download_filename, _public_lesson


def test_public_lesson_hides_answers_transcripts_and_paths():
    lesson = {
        "id": "00000000-0000-0000-0000-000000000001",
        "status": "ready",
        "platform": "Vimeo",
        "media_path": "/private/video.mp4",
        "caption_path": "/private/captions.vtt",
        "caption_source": "faster-whisper",
        "transcription": {
            "caption_path": "/private/generated.vtt",
            "caption_source": "faster-whisper",
            "model": "small",
        },
        "attempts": [],
        "exercises": [
            {
                "id": "ex-1",
                "expected": ["secret"],
                "transcript": "This transcript must stay hidden until the answer.",
                "display": "This [[blank:0]] must stay hidden.",
            }
        ],
    }

    public = _public_lesson(lesson)

    assert "media_path" not in public
    assert "caption_path" not in public
    assert "attempts" not in public
    assert "caption_path" not in public["transcription"]
    assert "expected" not in public["exercises"][0]
    assert "transcript" not in public["exercises"][0]
    assert public["media_url"].endswith("/media")
    assert public["download_url"].endswith("/download")
    assert public["platform"] == "Vimeo"


def test_download_filename_is_sanitized():
    lesson = {"title": "A/B:C*D? <lesson>"}
    filename = _download_filename(lesson, Path("video.mp4"))
    assert filename.endswith(".mp4")
    assert "/" not in filename
    assert ":" not in filename
