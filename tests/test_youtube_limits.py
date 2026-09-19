import pytest
from yt_dlp.utils import DownloadError

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
        youtube._preflight_once("https://example.com/video")


def test_preflight_rejects_overlong_video(monkeypatch):
    FakeYDL.payload = {"is_live": False, "duration": youtube.MAX_VIDEO_DURATION_SECONDS + 1}
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYDL)
    with pytest.raises(RuntimeError, match="demasiado largo"):
        youtube._preflight_once("https://example.com/video")


def test_youtube_preflight_falls_back_after_login_required(monkeypatch):
    attempted = []

    class ClientAwareYDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            assert download is False
            client = self.options["extractor_args"]["youtube"]["player_client"][0]
            attempted.append(client)
            if client == "web_embedded":
                raise DownloadError("Sign in to confirm you're not a bot")
            return {"id": "abc", "duration": 30, "is_live": False}

    monkeypatch.setattr(youtube, "YoutubeDL", ClientAwareYDL)
    info = youtube._preflight("https://www.youtube.com/watch?v=abc")

    assert attempted[:2] == ["web_embedded", "android_vr"]
    assert info["_freetuve_player_client"] == "android_vr"


def test_runtime_options_use_one_youtube_client_at_a_time(monkeypatch):
    monkeypatch.setattr(youtube, "POT_PROVIDER_URL", "http://pot-provider.railway.internal:4416")
    options = youtube._yt_dlp_runtime_options("mweb")

    assert options["extractor_args"]["youtube"]["player_client"] == ["mweb"]
    assert options["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == [
        "http://pot-provider.railway.internal:4416"
    ]


def test_youtube_candidate_order_prefers_successful_preflight_client():
    clients = youtube._youtube_client_candidates("tv")
    assert clients[0] == "tv"
    assert len(clients) == len(set(clients))
    assert set(clients) == set(youtube._YOUTUBE_CLIENTS)


def test_preflight_accepts_longer_movie_limit(monkeypatch):
    FakeYDL.payload = {"is_live": False, "duration": youtube.MAX_VIDEO_DURATION_SECONDS + 60}
    monkeypatch.setattr(youtube, "YoutubeDL", FakeYDL)
    info = youtube._preflight_once(
        "https://example.com/movie",
        max_duration_seconds=youtube.MAX_VIDEO_DURATION_SECONDS + 120,
    )
    assert info["duration"] == youtube.MAX_VIDEO_DURATION_SECONDS + 60
