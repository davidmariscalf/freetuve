from pathlib import Path

from .exercises import generate_exercises
from .storage import lesson_dir, load_lesson, save_lesson
from .vtt import build_segments, parse_vtt
from .youtube import download_video_and_captions


def process_lesson(lesson_id: str) -> None:
    lesson = load_lesson(lesson_id)
    lesson["status"] = "processing"
    lesson.pop("error", None)
    save_lesson(lesson)

    try:
        directory = lesson_dir(lesson_id)
        media = download_video_and_captions(
            lesson["source_url"],
            directory,
            lesson["language"],
        )
        vtt_text = Path(media["caption_path"]).read_text(encoding="utf-8", errors="replace")
        cues = parse_vtt(vtt_text)
        segments = build_segments(cues)
        if len(segments) < 5:
            raise RuntimeError(
                "Los subtítulos no contienen suficientes frases útiles para crear una lección."
            )

        exercises = generate_exercises(
            segments,
            lesson["difficulty"],
            lesson["max_items"],
        )
        if len(exercises) < 5:
            raise RuntimeError("No se pudieron generar suficientes ejercicios de calidad.")

        lesson.update({
            "status": "ready",
            "title": media["title"],
            "video_id": media["video_id"],
            "duration": media["duration"],
            "thumbnail": media["thumbnail"],
            "source_url": media["webpage_url"],
            "media_path": media["media_path"],
            "caption_path": media["caption_path"],
            "exercise_count": len(exercises),
            "exercises": exercises,
        })
        save_lesson(lesson)
    except Exception as exc:
        lesson = load_lesson(lesson_id)
        lesson["status"] = "error"
        lesson["error"] = str(exc)[:700]
        save_lesson(lesson)
