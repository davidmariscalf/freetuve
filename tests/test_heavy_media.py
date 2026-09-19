from pathlib import Path

import app.heavy_media as heavy_media


class FakeYDL:
    attempted_formats = []

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        assert download is True
        selector = self.options["format"]
        self.attempted_formats.append(selector)
        if selector.startswith("ba["):
            template = self.options["outtmpl"]
            Path(template.replace("%(ext)s", "m4a")).write_bytes(b"compact audio")
        return {
            "id": "abc",
            "title": "Heavy source",
            "duration": 1200,
            "webpage_url": url,
            "extractor_key": "Test",
        }


def test_heavy_source_falls_back_to_audio_without_raising_media_cap(tmp_path, monkeypatch):
    FakeYDL.attempted_formats = []
    monkeypatch.setattr(heavy_media, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(heavy_media.source, "validate_source_url", lambda url: url)
    monkeypatch.setattr(
        heavy_media.source,
        "_preflight",
        lambda _url, max_duration_seconds=None: {"id": "abc", "title": "Heavy source", "duration": 1200},
    )
    monkeypatch.setattr(heavy_media.source, "_is_youtube_url", lambda _url: False)
    monkeypatch.setattr(
        heavy_media.source,
        "_download_caption_best_effort",
        lambda *_args, **_kwargs: None,
    )

    result = heavy_media.download_media_and_captions(
        "https://example.com/video",
        tmp_path,
        "en",
    )

    assert result["media_kind"] == "audio"
    assert result["download_profile"] == "audio-only"
    assert Path(result["media_path"]).suffix == ".m4a"
    assert result["media_bytes"] < heavy_media.MAX_MEDIA_BYTES
    assert "height<=480" in FakeYDL.attempted_formats[0]
    assert FakeYDL.attempted_formats[-1].startswith("ba[")
