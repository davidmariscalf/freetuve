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
