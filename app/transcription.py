import gc
import importlib.util
import os
import subprocess
import threading
from functools import lru_cache
from pathlib import Path


_MODEL_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()


def transcription_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def normalize_language(language: str) -> str:
    return language.strip().replace("_", "-").split("-", 1)[0].casefold()


def _model_settings() -> tuple[str, str, str, str]:
    model_name = os.getenv("FREETUVE_WHISPER_MODEL", "small")
    device = os.getenv("FREETUVE_WHISPER_DEVICE", "cpu")
    compute_type = os.getenv(
        "FREETUVE_WHISPER_COMPUTE_TYPE",
        "int8" if device == "cpu" else "float16",
    )
    default_root = Path(os.getenv("FREETUVE_DATA_DIR", "data")) / "models"
    download_root = str(Path(os.getenv("FREETUVE_MODEL_DIR", default_root)).resolve())
    return model_name, device, compute_type, download_root


@lru_cache(maxsize=2)
def _load_model(model_name: str, device: str, compute_type: str, download_root: str):
    from faster_whisper import WhisperModel

    Path(download_root).mkdir(parents=True, exist_ok=True)
    return WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        download_root=download_root,
    )


def release_transcription_model() -> None:
    """Drop cached Whisper model memory once a lesson finishes.

    FreeTuve currently runs with a 1 GB Railway memory limit. Keeping the model
    resident between lessons leaves too little headroom for yt-dlp, FFmpeg and
    request handling. Model files remain cached on disk, so a later lesson can
    reload them without downloading them again.
    """
    with _MODEL_LOCK:
        with _INFERENCE_LOCK:
            _load_model.cache_clear()
    gc.collect()


def _timestamp(seconds: float) -> str:
    total_ms = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _write_vtt(cues: list[tuple[float, float, str]], output_path: Path) -> None:
    lines = ["WEBVTT", ""]
    for index, (start, end, text) in enumerate(cues, 1):
        lines.extend([
            str(index),
            f"{_timestamp(start)} --> {_timestamp(end)}",
            text,
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _segment_is_reliable(segment) -> bool:
    """Reject ASR output that is too uncertain to become an exercise answer."""
    avg_logprob = getattr(segment, "avg_logprob", None)
    no_speech_prob = getattr(segment, "no_speech_prob", None)
    compression_ratio = getattr(segment, "compression_ratio", None)

    if avg_logprob is not None and float(avg_logprob) < -1.0:
        return False
    if no_speech_prob is not None and float(no_speech_prob) > 0.65:
        return False
    if compression_ratio is not None and float(compression_ratio) > 2.8:
        return False

    words = getattr(segment, "words", None) or []
    probabilities = [
        float(word.probability)
        for word in words
        if getattr(word, "probability", None) is not None
    ]
    if probabilities and sum(probabilities) / len(probabilities) < 0.55:
        return False
    return True


def _collect_transcription(model, source: Path, language: str):
    segments, info = model.transcribe(
        str(source),
        language=normalize_language(language),
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        word_timestamps=True,
    )
    cues: list[tuple[float, float, str]] = []
    rejected = 0
    for segment in segments:
        text = " ".join(str(segment.text).split()).strip()
        if not text:
            continue
        if not _segment_is_reliable(segment):
            rejected += 1
            continue
        start = max(0.0, float(segment.start))
        end = max(start + 0.05, float(segment.end))
        cues.append((start, end, text))
    return cues, info, rejected


def _normalize_audio_for_whisper(media: Path, output: Path) -> None:
    output.unlink(missing_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("FFmpeg no pudo normalizar el audio para la transcripción.") from exc
    if completed.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        detail = (completed.stderr or "FFmpeg no produjo audio utilizable").strip()[-400:]
        raise RuntimeError(f"No se pudo normalizar el audio para transcribirlo: {detail}")


def transcribe_media_to_vtt(media_path: str | Path, output_path: str | Path, language: str) -> dict:
    media = Path(media_path).resolve()
    output = Path(output_path).resolve()
    if not media.exists() or not media.is_file():
        raise RuntimeError("No se encuentra el vídeo que se debe transcribir.")
    if not transcription_available():
        raise RuntimeError("El motor local de transcripción no está instalado.")

    model_name, device, compute_type, download_root = _model_settings()
    with _MODEL_LOCK:
        model = _load_model(model_name, device, compute_type, download_root)

    normalized_audio = output.with_suffix(".whisper.wav")
    used_normalized_audio = False
    with _INFERENCE_LOCK:
        try:
            cues, info, rejected = _collect_transcription(model, media, language)
        except Exception:
            try:
                _normalize_audio_for_whisper(media, normalized_audio)
                cues, info, rejected = _collect_transcription(model, normalized_audio, language)
                used_normalized_audio = True
            except Exception as retry_error:
                raise RuntimeError(
                    "La transcripción local falló incluso después de normalizar el audio con FFmpeg."
                ) from retry_error
            finally:
                normalized_audio.unlink(missing_ok=True)

    if not cues:
        raise RuntimeError("La transcripción local no detectó voz utilizable con suficiente confianza.")

    output.parent.mkdir(parents=True, exist_ok=True)
    _write_vtt(cues, output)
    return {
        "caption_path": str(output),
        "caption_source": "faster-whisper",
        "model": model_name,
        "detected_language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "segment_count": len(cues),
        "rejected_segment_count": rejected,
        "audio_normalized": used_normalized_audio,
    }
