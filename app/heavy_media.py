from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .config import MAX_MEDIA_BYTES
from . import youtube as source


_VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}
_AUDIO_SUFFIXES = {".m4a", ".mp3", ".opus", ".ogg", ".aac", ".flac", ".wav"}
_MEDIA_SUFFIXES = _VIDEO_SUFFIXES | _AUDIO_SUFFIXES

# Do not make a heavy source fit by increasing the server's storage/memory cap.
# Prefer progressively cheaper renditions and, as a last resort, audio only. The
# lesson engine needs speech, not 720p pixels, so this keeps useful long videos
# processable on the 1 GB worker without weakening the resource guard.
_DOWNLOAD_PROFILES: tuple[tuple[str, str, str], ...] = (
    (
        "compact-480p",
        "b[height<=480][ext=mp4]/b[height<=480]/18/bv*[height<=480]+ba",
        "video",
    ),
    (
        "compact-360p",
        "b[height<=360][ext=mp4]/b[height<=360]/18/bv*[height<=360]+ba",
        "video",
    ),
    ("lowest-video", "worst[ext=mp4]/worst", "video"),
    ("audio-only", "ba[ext=m4a]/ba/bestaudio", "audio"),
)


def _clear_media_outputs(directory: Path) -> None:
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("media.") or path.name.startswith("video."):
            if path.suffix.casefold() in _MEDIA_SUFFIXES or path.suffix.casefold() in {".part", ".ytdl"}:
                path.unlink(missing_ok=True)


def _media_files(directory: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.startswith("media.")
            and path.suffix.casefold() in _MEDIA_SUFFIXES
        ),
        key=lambda path: path.stat().st_size,
        reverse=True,
    )


def _download_options(
    directory: Path,
    format_selector: str,
    media_kind: str,
    player_client: str | None,
) -> dict:
    options = {
        "format": format_selector,
        "outtmpl": str(directory / "media.%(ext)s"),
        "noplaylist": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "overwrites": True,
        "concurrent_fragment_downloads": 1,
        "socket_timeout": 30,
        "max_filesize": MAX_MEDIA_BYTES,
        "allowed_extractors": source._allowed_extractors(),
        "retries": 4,
        "fragment_retries": 4,
        "extractor_retries": 2,
        **source._yt_dlp_runtime_options(player_client),
    }
    if media_kind == "video":
        options["merge_output_format"] = "mp4"
    return options


def _download_profile(
    url: str,
    directory: Path,
    profile_name: str,
    format_selector: str,
    media_kind: str,
    player_client: str | None,
) -> tuple[dict, Path] | None:
    _clear_media_outputs(directory)
    try:
        with YoutubeDL(
            _download_options(directory, format_selector, media_kind, player_client)
        ) as ydl:
            info = ydl.extract_info(url, download=True) or {}
    except DownloadError:
        return None

    candidates = _media_files(directory)
    if not candidates:
        return None
    media_path = candidates[0]
    if media_path.stat().st_size > MAX_MEDIA_BYTES:
        _clear_media_outputs(directory)
        return None
    info["_freetuve_download_profile"] = profile_name
    info["_freetuve_media_kind"] = media_kind
    return info, media_path


def download_media_and_captions(url: str, directory: Path, language: str) -> dict:
    source.validate_source_url(url)
    directory.mkdir(parents=True, exist_ok=True)
    preflight = source._preflight(url)
    preferred_client = preflight.get("_freetuve_player_client")

    if source._is_youtube_url(url):
        clients: tuple[str | None, ...] = source._youtube_client_candidates(preferred_client)
    else:
        clients = (None,)

    selected: tuple[dict, Path] | None = None
    successful_client: str | None = None
    selected_profile = ""
    selected_kind = "video"

    # Profile-first ordering means we retain video whenever a bounded rendition
    # exists. Only after every supported client fails at that quality do we step
    # down, with audio-only as the final bounded fallback.
    for profile_name, format_selector, media_kind in _DOWNLOAD_PROFILES:
        for client in clients:
            selected = _download_profile(
                url,
                directory,
                profile_name,
                format_selector,
                media_kind,
                client,
            )
            if selected is not None:
                successful_client = client
                selected_profile = profile_name
                selected_kind = media_kind
                break
        if selected is not None:
            break

    if selected is None:
        _clear_media_outputs(directory)
        max_mb = MAX_MEDIA_BYTES // (1024 * 1024)
        raise RuntimeError(
            "No se encontró una versión del vídeo que quepa de forma segura en el servidor. "
            f"FreeTuve probó calidades reducidas y audio; el límite de procesamiento es {max_mb} MB."
        )

    info, media_path = selected
    caption = source._download_caption_best_effort(
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
        "webpage_url": source._safe_webpage_url(merged_info, url),
        "platform": source._platform_name(merged_info, url),
        "media_path": str(media_path.resolve()),
        "media_kind": selected_kind,
        "media_bytes": media_path.stat().st_size,
        "download_profile": selected_profile,
        "caption_path": str(caption.resolve()) if caption else None,
        "player_client": successful_client,
    }
