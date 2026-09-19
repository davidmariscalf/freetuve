from __future__ import annotations

import ipaddress
import shutil
import socket
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .config import (
    ALLOW_GENERIC_EXTRACTOR,
    MAX_MEDIA_BYTES,
    MAX_VIDEO_DURATION_SECONDS,
    POT_PROVIDER_URL,
)


MEDIA_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}
_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".home", ".lan")
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
# YouTube can reject one Innertube client before a PO token can even be minted.
# Try clients independently so one LOGIN_REQUIRED response does not abort the
# whole request. The order favors clients that currently need no GVS token,
# with mweb + our PO-token provider as an additional path.
_YOUTUBE_CLIENTS = ("web_embedded", "android_vr", "tv", "mweb", "web_safari")


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


def _is_youtube_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return host in _YOUTUBE_HOSTS or host.endswith(".youtube.com")


def _allowed_extractors() -> list[str]:
    # The generic extractor is useful for self-hosted/trusted deployments, but on a
    # public server it would turn arbitrary URLs into outbound fetches. Built-in
    # site extractors already cover a very large number of services.
    return ["default"] if ALLOW_GENERIC_EXTRACTOR else ["default", "-generic"]


def _yt_dlp_runtime_options(player_client: str | None = None) -> dict:
    options: dict = {}
    node_path = shutil.which("node")
    if node_path:
        options["js_runtimes"] = {"node": {"path": node_path}}

    extractor_args: dict[str, dict[str, list[str]]] = {}
    if player_client:
        extractor_args["youtube"] = {"player_client": [player_client]}
    if POT_PROVIDER_URL:
        extractor_args["youtubepot-bgutilhttp"] = {"base_url": [POT_PROVIDER_URL]}
    if extractor_args:
        options["extractor_args"] = extractor_args
    return options


def _friendly_download_error(exc: DownloadError, *, downloading: bool) -> str:
    message = str(exc).replace("’", "'").casefold()
    if "confirm you're not a bot" in message or "login_required" in message:
        if POT_PROVIDER_URL:
            return (
                "YouTube está rechazando temporalmente esta ruta de conexión del servidor. "
                "FreeTuve probará automáticamente rutas alternativas cuando estén disponibles."
            )
        return (
            "YouTube está bloqueando temporalmente las conexiones del servidor. "
            "No es un problema con tu enlace; prueba de nuevo más tarde o usa otro vídeo."
        )
    if downloading:
        return (
            "No se pudo descargar el vídeo desde esa plataforma. Puede requerir autenticación, "
            "usar DRM o haber cambiado su formato."
        )
    return (
        "No se pudo abrir ese vídeo. La plataforma puede no ser compatible, exigir inicio de sesión "
        "o haber cambiado su reproductor."
    )


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


def _validate_preflight_info(info: dict | None, max_duration_seconds: int | None = None) -> dict:
    if not info:
        raise RuntimeError("La plataforma no devolvió información de vídeo utilizable.")
    if info.get("_type") in {"playlist", "multi_video"}:
        raise RuntimeError("Pega el enlace de un vídeo individual, no una lista o colección.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise RuntimeError("Los directos y estrenos en curso no son compatibles todavía.")

    duration = info.get("duration")
    duration_limit = int(max_duration_seconds or MAX_VIDEO_DURATION_SECONDS)
    if duration and float(duration) > duration_limit:
        minutes = duration_limit // 60
        raise RuntimeError(f"El contenido es demasiado largo. El máximo configurado es de {minutes} minutos.")
    return info


def _preflight_once(
    url: str,
    player_client: str | None = None,
    max_duration_seconds: int | None = None,
) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 30,
        "allowed_extractors": _allowed_extractors(),
        "extractor_retries": 2,
        **_yt_dlp_runtime_options(player_client),
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise RuntimeError(_friendly_download_error(exc, downloading=False)) from exc
    return _validate_preflight_info(info, max_duration_seconds=max_duration_seconds)


def _youtube_client_candidates(preferred: str | None = None) -> tuple[str, ...]:
    if preferred not in _YOUTUBE_CLIENTS:
        return _YOUTUBE_CLIENTS
    return (preferred, *tuple(client for client in _YOUTUBE_CLIENTS if client != preferred))


def _preflight(url: str, max_duration_seconds: int | None = None) -> dict:
    if not _is_youtube_url(url):
        return _preflight_once(url, max_duration_seconds=max_duration_seconds)

    errors: list[str] = []
    for client in _YOUTUBE_CLIENTS:
        try:
            info = _preflight_once(url, client, max_duration_seconds=max_duration_seconds)
            info["_freetuve_player_client"] = client
            return info
        except RuntimeError as exc:
            errors.append(str(exc))

    # Every supported YouTube client failed. Keep the message actionable but do
    # not imply the URL itself is broken when the common cause is IP reputation.
    if any("YouTube" in error for error in errors):
        raise RuntimeError(
            "YouTube ha rechazado todas las rutas de reproducción disponibles desde el servidor. "
            "FreeTuve ya probó varios clientes y el proveedor de tokens automáticamente; "
            "el bloqueo depende de YouTube y de la IP del servidor."
        )
    raise RuntimeError(errors[-1] if errors else "No se pudo abrir el vídeo de YouTube.")


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


def _clear_video_outputs(directory: Path) -> None:
    for path in directory.glob("video.*"):
        if path.is_file():
            path.unlink(missing_ok=True)


def _download_options(directory: Path, player_client: str | None = None) -> dict:
    return {
        # Prefer a single <=720p stream because it is less fragile across the
        # current YouTube clients. Fall back to merged video+audio where needed.
        "format": (
            "b[height<=720][ext=mp4]/b[height<=720]/18/"
            "bv*[height<=720]+ba/bv*+ba/b"
        ),
        "outtmpl": str(directory / "video.%(ext)s"),
        "noplaylist": True,
        # Captions are fetched separately as best-effort evidence. A subtitle
        # endpoint failure must not throw away an otherwise usable video.
        "writesubtitles": False,
        "writeautomaticsub": False,
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "overwrites": True,
        "concurrent_fragment_downloads": 2,
        "socket_timeout": 30,
        "max_filesize": MAX_MEDIA_BYTES,
        "allowed_extractors": _allowed_extractors(),
        "retries": 4,
        "fragment_retries": 4,
        "extractor_retries": 2,
        **_yt_dlp_runtime_options(player_client),
    }


def _download_once(url: str, directory: Path, player_client: str | None = None) -> dict:
    try:
        with YoutubeDL(_download_options(directory, player_client)) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise RuntimeError(_friendly_download_error(exc, downloading=True)) from exc
    return info or {}


def _download_caption_best_effort(
    url: str,
    directory: Path,
    language: str,
    player_client: str | None,
) -> Path | None:
    clients: tuple[str | None, ...]
    if _is_youtube_url(url):
        clients = _youtube_client_candidates(player_client)
    else:
        clients = (None,)

    for client in clients:
        options = {
            "outtmpl": str(directory / "video.%(ext)s"),
            "noplaylist": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [language],
            "subtitlesformat": "vtt",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 20,
            "allowed_extractors": _allowed_extractors(),
            "extractor_retries": 1,
            **_yt_dlp_runtime_options(client),
        }
        try:
            with YoutubeDL(options) as ydl:
                ydl.extract_info(url, download=True)
        except DownloadError:
            continue
        caption = _pick_caption(directory, language)
        if caption:
            return caption
    return _pick_caption(directory, language)


def download_media_and_captions(url: str, directory: Path, language: str) -> dict:
    validate_source_url(url)
    directory.mkdir(parents=True, exist_ok=True)
    preflight = _preflight(url)
    preferred_client = preflight.get("_freetuve_player_client")

    if _is_youtube_url(url):
        clients: tuple[str | None, ...] = _youtube_client_candidates(preferred_client)
    else:
        clients = (None,)

    info: dict = {}
    last_error: RuntimeError | None = None
    successful_client: str | None = None
    for client in clients:
        _clear_video_outputs(directory)
        try:
            info = _download_once(url, directory, client)
            successful_client = client
            break
        except RuntimeError as exc:
            last_error = exc

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
        if last_error is not None:
            raise last_error
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

    caption = _download_caption_best_effort(
        url,
        directory,
        language,
        successful_client,
    )
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
        "player_client": successful_client,
    }


# Compatibility alias while downstream imports migrate to the generic name.
def download_video_and_captions(url: str, directory: Path, language: str) -> dict:
    return download_media_and_captions(url, directory, language)
