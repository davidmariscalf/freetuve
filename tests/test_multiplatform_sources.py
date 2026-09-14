import socket

import pytest

import app.youtube as media


def _public_dns(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _private_dns(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]


def test_validate_source_accepts_public_https(monkeypatch):
    monkeypatch.setattr(media.socket, "getaddrinfo", _public_dns)
    url = "https://vimeo.com/123456"
    assert media.validate_source_url(url) == url


def test_validate_source_rejects_http(monkeypatch):
    monkeypatch.setattr(media.socket, "getaddrinfo", _public_dns)
    with pytest.raises(ValueError, match="HTTPS"):
        media.validate_source_url("http://example.com/video")


def test_validate_source_rejects_private_addresses(monkeypatch):
    monkeypatch.setattr(media.socket, "getaddrinfo", _private_dns)
    with pytest.raises(ValueError, match="privadas"):
        media.validate_source_url("https://example.com/video")


def test_validate_source_rejects_credentials(monkeypatch):
    monkeypatch.setattr(media.socket, "getaddrinfo", _public_dns)
    with pytest.raises(ValueError, match="credenciales"):
        media.validate_source_url("https://user:pass@example.com/video")


def test_public_server_disables_generic_extractor(monkeypatch):
    monkeypatch.setattr(media, "ALLOW_GENERIC_EXTRACTOR", False)
    assert media._allowed_extractors() == ["default", "-generic"]


def test_trusted_self_host_can_enable_generic_extractor(monkeypatch):
    monkeypatch.setattr(media, "ALLOW_GENERIC_EXTRACTOR", True)
    assert media._allowed_extractors() == ["default"]


def test_final_media_size_is_enforced_after_download(tmp_path, monkeypatch):
    class FakeDownloadYDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            assert download is True
            output = tmp_path / "video.mp4"
            output.write_bytes(b"x" * 11)
            return {
                "id": "video-id",
                "title": "Example",
                "duration": 30,
                "extractor_key": "Example",
                "webpage_url": "https://example.com/video",
            }

    monkeypatch.setattr(media, "YoutubeDL", FakeDownloadYDL)
    monkeypatch.setattr(media, "MAX_MEDIA_BYTES", 10)
    monkeypatch.setattr(media, "validate_source_url", lambda url: url)
    monkeypatch.setattr(media, "_preflight", lambda _url: {"duration": 30})

    with pytest.raises(RuntimeError, match="supera el límite"):
        media.download_media_and_captions("https://example.com/video", tmp_path, "en")

    assert not (tmp_path / "video.mp4").exists()
