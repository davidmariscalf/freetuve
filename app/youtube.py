from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from .config import MAX_MEDIA_BYTES, MAX_VIDEO_DURATION_SECONDS


ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
MEDIA_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}


def validate_youtube_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ValueError("Introduce una URL HTTPS válida de YouTube.")
    return url


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
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise RuntimeError("Los directos y estrenos en curso no son compatibles todavía.")
    duration = info.get("duration")
    if duration and float(duration) > MAX_VIDEO_DURATION_SECONDS:
        minutes = MAX_VIDEO_DURATION_SECONDS // 60
        raise RuntimeError(f"El vídeo es demasiado largo. El máximo configurado es de {minutes} minutos.")
    return info


def download_video_and_captions(url: str, directory: Path, language: str) -> dict:
    validate_youtube_url(url)
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
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

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

    caption = _pick_caption(directory, language)
    return {
        "title": info.get("title") or preflight.get("title") or "Lección sin título",
        "video_id": info.get("id") or preflight.get("id"),
        "duration": info.get("duration") or preflight.get("duration"),
        "thumbnail": info.get("thumbnail") or preflight.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or preflight.get("webpage_url") or url,
        "media_path": str(media_files[0].resolve()),
        "caption_path": str(caption.resolve()) if caption else None,
    }
