from pathlib import Path

from .exercises import generate_exercises
from .storage import lesson_dir, load_lesson, save_lesson
from .transcription import transcribe_media_to_vtt
from .vtt import build_segments, parse_vtt
from .youtube import download_media_and_captions


def _segments_from_vtt(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return build_segments(parse_vtt(text))


def process_lesson(lesson_id: str) -> None:
    try:
        lesson = load_lesson(lesson_id)
        lesson["status"] = "processing"
        lesson.pop("error", None)
        save_lesson(lesson)
    except FileNotFoundError:
        return

    try:
        directory = lesson_dir(lesson_id)
        media = download_media_and_captions(
            lesson["source_url"],
            directory,
            lesson["language"],
        )

        caption_path = media.get("caption_path")
        caption_source = "source"
        segments = _segments_from_vtt(caption_path) if caption_path else []
        transcription = None

        if len(segments) < 5:
            generated_caption = directory / "generated.transcript.vtt"
            transcription_result = transcribe_media_to_vtt(
                media["media_path"],
                generated_caption,
                lesson["language"],
            )
            caption_path = transcription_result["caption_path"]
            caption_source = transcription_result["caption_source"]
            transcription = {
                key: value
                for key, value in transcription_result.items()
                if key != "caption_path"
            }
            segments = _segments_from_vtt(caption_path)

        if len(segments) < 5:
            raise RuntimeError(
                "No se detectaron suficientes frases útiles para crear una lección."
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
            "platform": media.get("platform") or "web",
            "duration": media["duration"],
            "thumbnail": media["thumbnail"],
            "source_url": media["webpage_url"],
            "media_path": media["media_path"],
            "caption_path": caption_path,
            "caption_source": caption_source,
            "transcription": transcription,
            "exercise_count": len(exercises),
            "exercises": exercises,
        })
        save_lesson(lesson)
    except FileNotFoundError:
        return
    except Exception as exc:
        try:
            lesson = load_lesson(lesson_id)
        except FileNotFoundError:
            return
        lesson["status"] = "error"
        lesson["error"] = str(exc)[:700]
        try:
            save_lesson(lesson)
        except FileNotFoundError:
            return
