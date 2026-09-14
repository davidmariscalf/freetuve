from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL


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
    preferred = [p for p in candidates if f".{lang}." in p.name.casefold() or p.name.casefold().endswith(f".{lang}.vtt")]
    return (preferred or candidates)[0]


def download_video_and_captions(url: str, directory: Path, language: str) -> dict:
    validate_youtube_url(url)
    directory.mkdir(parents=True, exist_ok=True)

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
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    media_files = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.casefold() in MEDIA_SUFFIXES),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not media_files:
        raise RuntimeError("No se pudo obtener un archivo de vídeo reproducible.")

    caption = _pick_caption(directory, language)
    if caption is None:
        raise RuntimeError(
            "Este vídeo no ofrece subtítulos utilizables en el idioma elegido. "
            "Prueba otro vídeo o un idioma con subtítulos disponibles."
        )

    return {
        "title": info.get("title") or "Lección sin título",
        "video_id": info.get("id"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or url,
        "media_path": str(media_files[0].resolve()),
        "caption_path": str(caption.resolve()),
    }
