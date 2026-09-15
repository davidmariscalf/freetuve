from types import SimpleNamespace

import app.transcription as transcription
from app.vtt import build_segments, parse_vtt


class FakeSegment:
    def __init__(self, start, end, text, **confidence):
        self.start = start
        self.end = end
        self.text = text
        for key, value in confidence.items():
            setattr(self, key, value)


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


class FlakyAudioModel(FakeModel):
    def __init__(self):
        self.calls = []

    def transcribe(self, media_path, **kwargs):
        self.calls.append(media_path)
        if len(self.calls) == 1:
            raise ValueError("Frame does not match AudioFifo parameters")
        return super().transcribe(media_path, **kwargs)


class ConfidenceModel(FakeModel):
    def transcribe(self, media_path, **kwargs):
        good_words = [SimpleNamespace(probability=0.94), SimpleNamespace(probability=0.91)]
        bad_words = [SimpleNamespace(probability=0.20), SimpleNamespace(probability=0.24)]
        segments = iter([
            FakeSegment(
                0.0,
                2.0,
                "Hallucinated uncertain words.",
                avg_logprob=-1.4,
                no_speech_prob=0.1,
                compression_ratio=1.0,
                words=bad_words,
            ),
            FakeSegment(
                2.1,
                4.1,
                "Clear spoken sentence.",
                avg_logprob=-0.2,
                no_speech_prob=0.02,
                compression_ratio=1.1,
                words=good_words,
            ),
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
    assert result["audio_normalized"] is False
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.100" in text

    cues = parse_vtt(text)
    assert len(cues) == 5
    segments = build_segments(cues)
    assert len(segments) >= 4
    assert "subtitles locally" in " ".join(item["text"] for item in segments)


def test_low_confidence_asr_segment_is_not_written(tmp_path, monkeypatch):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"fake")
    output = tmp_path / "generated.vtt"

    monkeypatch.setattr(transcription, "transcription_available", lambda: True)
    monkeypatch.setattr(transcription, "_load_model", lambda *args: ConfidenceModel())

    result = transcription.transcribe_media_to_vtt(media, output, "en")
    text = output.read_text(encoding="utf-8")

    assert result["segment_count"] == 1
    assert result["rejected_segment_count"] == 1
    assert "Clear spoken sentence." in text
    assert "Hallucinated uncertain words." not in text


def test_transcription_retries_with_ffmpeg_normalized_audio(tmp_path, monkeypatch):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"fake")
    output = tmp_path / "generated.vtt"
    model = FlakyAudioModel()

    monkeypatch.setattr(transcription, "transcription_available", lambda: True)
    monkeypatch.setattr(transcription, "_load_model", lambda *args: model)

    def fake_normalize(_media, normalized):
        normalized.write_bytes(b"normalized")

    monkeypatch.setattr(transcription, "_normalize_audio_for_whisper", fake_normalize)

    result = transcription.transcribe_media_to_vtt(media, output, "en")

    assert result["audio_normalized"] is True
    assert len(model.calls) == 2
    assert model.calls[1].endswith(".whisper.wav")
    assert not output.with_suffix(".whisper.wav").exists()
    assert output.exists()
