import pytest

import app.youtube as youtube


class FakeYDL:
    payload = {}

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        assert download is False
        return dict(self.payload)


def test_preflight_rejects_live_video(monkeypatch):
    FakeYDL.payload = {"is_live": True, "duration": 100}
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYDL)
    with pytest.raises(RuntimeError, match="directos"):
        youtube._preflight("https://youtu.be/test")


def test_preflight_rejects_overlong_video(monkeypatch):
    FakeYDL.payload = {"is_live": False, "duration": youtube.MAX_VIDEO_DURATION_SECONDS + 1}
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYDL)
    with pytest.raises(RuntimeError, match="demasiado largo"):
        youtube._preflight("https://youtu.be/test")
