from types import SimpleNamespace

import app.transcription as transcription
from app.vtt import build_segments, parse_vtt


class FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class FakeModel:
    def transcribe(self, media_path, **kwargs):
        segments = iter([
            FakeSegment(0.0, 2.1, "Hello there."),
            FakeSegment(2.2, 4.5, "This is a useful listening exercise."),
            FakeSegment(4.6, 7.0, "We can generate subtitles locally."),
            FakeSegment(7.1, 9.6, "The learner listens before reading."),
            FakeSegment(9.7, 12.4, "Then the full sentence is revealed."),
        ])
        info = SimpleNamespace(language="en", language_probability=0.99)
        return segments, info


def test_language_normalization():
    assert transcription.normalize_language("en-US") == "en"
    assert transcription.normalize_language("pt_BR") == "pt"


def test_local_transcription_writes_parseable_vtt(tmp_path, monkeypatch):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"fake")
    output = tmp_path / "generated.vtt"

    monkeypatch.setattr(transcription, "transcription_available", lambda: True)
    monkeypatch.setattr(transcription, "_load_model", lambda *args: FakeModel())

    result = transcription.transcribe_media_to_vtt(media, output, "en-US")

    assert result["caption_source"] == "faster-whisper"
    assert result["detected_language"] == "en"
    assert result["segment_count"] == 5
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.100" in text

    segments = build_segments(parse_vtt(text))
    assert len(segments) >= 5
    assert "subtitles locally" in " ".join(item["text"] for item in segments)
