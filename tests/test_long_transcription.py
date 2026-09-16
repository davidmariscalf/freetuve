from pathlib import Path
from types import SimpleNamespace

import app.transcription as transcription


def test_long_media_is_transcribed_in_bounded_chunks(tmp_path, monkeypatch):
    media = tmp_path / "media.mp4"
    media.write_bytes(b"fake")
    output = tmp_path / "generated.vtt"

    monkeypatch.setattr(transcription, "transcription_available", lambda: True)
    monkeypatch.setattr(transcription, "_load_model", lambda *args: object())

    extracted = []

    def fake_extract(_media, chunk_path, **kwargs):
        extracted.append((Path(chunk_path), kwargs))
        Path(chunk_path).write_bytes(b"wav")

    monkeypatch.setattr(transcription, "_run_ffmpeg_audio_extract", fake_extract)
    monkeypatch.setattr(
        transcription,
        "_collect_transcription",
        lambda *_args, **_kwargs: (
            [(5.0, 7.0, "Reliable chunk sentence.")],
            SimpleNamespace(language="en", language_probability=0.99),
            0,
        ),
    )

    result = transcription.transcribe_media_to_vtt(
        media,
        output,
        "en",
        duration_seconds=1300,
    )

    assert result["chunked"] is True
    assert result["transcription_chunks"] == 3
    assert result["audio_normalized"] is True
    assert len(extracted) == 3
    assert all(not chunk_path.exists() for chunk_path, _kwargs in extracted)

    text = output.read_text(encoding="utf-8")
    assert "00:00:05.000 --> 00:00:07.000" in text
    assert "00:10:03.000 --> 00:10:05.000" in text
    assert "00:20:03.000 --> 00:20:05.000" in text
