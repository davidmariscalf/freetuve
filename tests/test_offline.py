from pathlib import Path
from uuid import uuid4

import app.offline as offline


def test_offline_pack_contains_only_public_learning_data(tmp_path, monkeypatch):
    lesson_id = str(uuid4())
    root = tmp_path / lesson_id
    root.mkdir()
    media = root / "video.mp4"
    media.write_bytes(b"video")

    monkeypatch.setattr(offline, "lesson_dir", lambda _: root)

    def fake_clip(media_path: Path, output_path: Path, start: float, end: float):
        assert media_path == media.resolve()
        assert end > start
        output_path.write_bytes(b"audio")

    monkeypatch.setattr(offline, "_make_clip", fake_clip)

    lesson = {
        "id": lesson_id,
        "status": "ready",
        "title": "Test lesson",
        "language": "en",
        "difficulty": "medium",
        "source_type": "movie",
        "caption_source": "youtube",
        "media_path": str(media.resolve()),
        "caption_path": str((root / "secret.vtt").resolve()),
        "exercises": [
            {
                "id": "ex-1",
                "start": 1.0,
                "end": 3.0,
                "type": "cloze",
                "display": "Hello [[blank:0]]",
                "blank_count": 1,
                "choices": [],
                "expected": ["world"],
                "transcript": "Hello world",
                "min_listens": 2,
            }
        ],
    }

    pack = offline.build_offline_pack(lesson)
    assert pack["offline_schema"] == 1
    assert pack["source_type"] == "movie"
    assert pack["size_bytes"] == 5
    assert pack["exercises"][0]["expected"] == ["world"]
    assert pack["exercises"][0]["clip_url"].endswith("/clip-001.m4a")
    dumped = str(pack)
    assert str(media.resolve()) not in dumped
    assert "secret.vtt" not in dumped
