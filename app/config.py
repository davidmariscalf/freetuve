import os

APP_VERSION = "1.2.4"


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


MAX_VIDEO_DURATION_SECONDS = _int_env("FREETUVE_MAX_VIDEO_SECONDS", 3600, 60, 14400)
MAX_MEDIA_BYTES = _int_env("FREETUVE_MAX_MEDIA_MB", 750, 50, 5000) * 1024 * 1024
LESSON_TTL_HOURS = _int_env("FREETUVE_LESSON_TTL_HOURS", 24, 1, 720)
CLEANUP_INTERVAL_SECONDS = _int_env("FREETUVE_CLEANUP_INTERVAL_SECONDS", 3600, 60, 86400)
CREATE_LIMIT_PER_HOUR = _int_env("FREETUVE_CREATE_LIMIT_PER_HOUR", 10, 1, 1000)
OFFLINE_AUDIO_BITRATE_KBPS = _int_env("FREETUVE_OFFLINE_AUDIO_KBPS", 64, 32, 192)
ALLOW_GENERIC_EXTRACTOR = _bool_env("FREETUVE_ALLOW_GENERIC_EXTRACTOR", False)
POT_PROVIDER_URL = os.getenv("FREETUVE_POT_PROVIDER_URL", "").strip().rstrip("/")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FREETUVE_ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,https://freetuve.netlify.app",
    ).split(",")
    if origin.strip()
]
