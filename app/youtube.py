from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .config import ALLOW_GENERIC_EXTRACTOR, MAX_MEDIA_BYTES, MAX_VIDEO_DURATION_SECONDS


MEDIA_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}
_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".home", ".lan")
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


def _resolve_public_host(host: str, port: int = 443) -> None:
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_HOST_SUFFIXES):
        raise ValueError("La dirección indicada no es una plataforma pública válida.")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("No se pudo resolver el dominio de la URL.") from exc
    if not addresses:
        raise ValueError("No se pudo resolver el dominio de la URL.")

    for address in addresses:
        raw_ip = address[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise ValueError("La URL resolvió a una dirección no válida.") from exc
        if not ip.is_global:
            raise ValueError("Por seguridad no se permiten direcciones privadas, locales o reservadas.")


def validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host:
        raise ValueError("Introduce una URL HTTPS válida de una plataforma de vídeo.")
    if parsed.username or parsed.password:
        raise ValueError("No se permiten credenciales dentro de la URL.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("El puerto de la URL no es válido.") from exc
    if port not in {None, 443}:
        raise ValueError("Solo se permiten URLs HTTPS por el puerto estándar.")
    _resolve_public_host(host, 443)
    return url


# Compatibility alias for code that used the old YouTube-only name.
def validate_youtube_url(url: str) -> str:
    return validate_source_url(url)


def _allowed_extractors() -> list[str]:
    # The generic extractor is useful for self-hosted/trusted deployments, but on a
    # public server it would turn arbitrary URLs into outbound fetches. Built-in
    # site extractors already cover a very large number of services.
    return ["default"] if ALLOW_GENERIC_EXTRACTOR else ["default", "-generic"]


def _pick_caption(directory: Path, language: str) -> Path | None:
    candidates = sorted(directory.glob("*.vtt"))
    if not candidates:
        return None
    lang = language.casefold()
    preferred = [
        p
        for p in candidates
        if f".{lang}." in p.name.casefold()
        or p.name.casefold().endswith(f".{lang}.vtt")
    ]
    return (preferred or candidates)[0]


def _preflight(url: str) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 30,
        "allowed_extractors": _allowed_extractors(),
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise RuntimeError(
            "No se pudo abrir ese vídeo. La plataforma puede no ser compatible, exigir inicio de sesión o haber cambiado su reproductor."
        ) from exc

    if not info:
        raise RuntimeError("La plataforma no devolvió información de vídeo utilizable.")
    if info.get("_type") in {"playlist", "multi_video"}:
        raise RuntimeError("Pega el enlace de un vídeo individual, no una lista o colección.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise RuntimeError("Los directos y estrenos en curso no son compatibles todavía.")

    duration = info.get("duration")
    if duration and float(duration) > MAX_VIDEO_DURATION_SECONDS:
        minutes = MAX_VIDEO_DURATION_SECONDS // 60
        raise RuntimeError(f"El vídeo es demasiado largo. El máximo configurado es de {minutes} minutos.")
    return info


def _safe_webpage_url(info: dict, fallback: str) -> str:
    candidate = info.get("webpage_url")
    if not isinstance(candidate, str):
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return fallback
    return candidate


def _platform_name(info: dict, url: str) -> str:
    value = info.get("extractor_key") or info.get("extractor")
    if value:
        return str(value)
    return (urlparse(url).hostname or "web").removeprefix("www.")


def download_media_and_captions(url: str, directory: Path, language: str) -> dict:
    validate_source_url(url)
    directory.mkdir(parents=True, exist_ok=True)
    preflight = _preflight(url)

    options = {
        "format": (
            "bv*[height<=720][vcodec^=avc1]+ba[acodec^=mp4a]/"
            "b[height<=720][ext=mp4]/bv*[height<=720]+ba/b"
        ),
        "outtmpl": str(directory / "video.%(ext)s"),
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language, f"{language}.*"],
        "subtitlesformat": "vtt",
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "overwrites": True,
        "concurrent_fragment_downloads": 4,
        "socket_timeout": 30,
        "max_filesize": MAX_MEDIA_BYTES,
        "allowed_extractors": _allowed_extractors(),
        "retries": 3,
        "fragment_retries": 3,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise RuntimeError(
            "No se pudo descargar el vídeo desde esa plataforma. Puede requerir autenticación, usar DRM o haber cambiado su formato."
        ) from exc

    media_files = sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.casefold() in MEDIA_SUFFIXES
        ),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not media_files:
        max_mb = MAX_MEDIA_BYTES // (1024 * 1024)
        raise RuntimeError(
            f"No se pudo obtener un vídeo reproducible. Puede superar el límite de {max_mb} MB o no estar disponible."
        )

    media_path = media_files[0]
    if media_path.stat().st_size > MAX_MEDIA_BYTES:
        for path in media_files:
            path.unlink(missing_ok=True)
        max_mb = MAX_MEDIA_BYTES // (1024 * 1024)
        raise RuntimeError(f"El vídeo supera el límite configurado de {max_mb} MB.")

    caption = _pick_caption(directory, language)
    merged_info = info or preflight
    return {
        "title": merged_info.get("title") or preflight.get("title") or "Lección sin título",
        "video_id": merged_info.get("id") or preflight.get("id"),
        "duration": merged_info.get("duration") or preflight.get("duration"),
        "thumbnail": merged_info.get("thumbnail") or preflight.get("thumbnail"),
        "webpage_url": _safe_webpage_url(merged_info, url),
        "platform": _platform_name(merged_info, url),
        "media_path": str(media_path.resolve()),
        "caption_path": str(caption.resolve()) if caption else None,
    }


# Compatibility alias while downstream imports migrate to the generic name.
def download_video_and_captions(url: str, directory: Path, language: str) -> dict:
    return download_media_and_captions(url, directory, language)
