from __future__ import annotations

import subprocess
from pathlib import Path

from .config import OFFLINE_AUDIO_BITRATE_KBPS
from .storage import lesson_dir


def _clip_name(index: int) -> str:
    return f"clip-{index:03d}.m4a"


def _make_clip(media_path: Path, output_path: Path, start: float, end: float) -> None:
    duration = max(0.2, float(end) - float(start))
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(0.0, float(start) - 0.08):.3f}",
        "-i",
        str(media_path),
        "-t",
        f"{duration + 0.16:.3f}",
        "-vn",
        "-c:a",
        "aac",
        "-b:a",
        f"{OFFLINE_AUDIO_BITRATE_KBPS}k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        detail = (completed.stderr or "FFmpeg no pudo crear el fragmento").strip()[-500:]
        raise RuntimeError(f"No se pudo preparar el audio offline: {detail}")


def build_offline_pack(lesson: dict) -> dict:
    if lesson.get("status") != "ready" or not lesson.get("media_path"):
        raise RuntimeError("La lección todavía no está lista para guardarse sin conexión.")

    media_path = Path(lesson["media_path"]).resolve()
    root = lesson_dir(lesson["id"]).resolve()
    if root not in media_path.parents or not media_path.is_file():
        raise RuntimeError("El vídeo temporal ya no está disponible en el servidor.")

    output_dir = root / "offline"
    output_dir.mkdir(parents=True, exist_ok=True)
    exercises = []

    for index, exercise in enumerate(lesson.get("exercises", []), 1):
        filename = _clip_name(index)
        output_path = output_dir / filename
        if not output_path.exists() or output_path.stat().st_size == 0:
            _make_clip(media_path, output_path, exercise["start"], exercise["end"])

        exercises.append({
            "id": exercise["id"],
            "type": exercise["type"],
            "display": exercise["display"],
            "blank_count": exercise.get("blank_count", 0),
            "choices": exercise.get("choices", []),
            "expected": exercise["expected"],
            "transcript": exercise.get("transcript", ""),
            "min_listens": exercise.get("min_listens", 2),
            "clip_url": f"/api/lessons/{lesson['id']}/offline/{filename}",
        })

    total_bytes = sum(path.stat().st_size for path in output_dir.glob("*.m4a") if path.is_file())
    return {
        "offline_schema": 1,
        "id": lesson["id"],
        "title": lesson.get("title") or "Lección",
        "language": lesson.get("language"),
        "difficulty": lesson.get("difficulty"),
        "caption_source": lesson.get("caption_source"),
        "exercise_count": len(exercises),
        "size_bytes": total_bytes,
        "exercises": exercises,
    }


def offline_clip_path(lesson_id: str, filename: str) -> Path:
    if not filename.startswith("clip-") or not filename.endswith(".m4a") or "/" in filename or "\\" in filename:
        raise ValueError("Nombre de fragmento no válido")
    root = (lesson_dir(lesson_id) / "offline").resolve()
    path = (root / filename).resolve()
    if root not in path.parents:
        raise ValueError("Ruta de fragmento no válida")
    return path
