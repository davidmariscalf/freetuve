from pathlib import Path

from .exercises import generate_exercises
from .fidelity import verify_segments
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

        # Source captions are useful evidence, but they are not authoritative:
        # automatic captions can be wrong in exactly the words a listening
        # exercise asks the learner to type. Always derive the exercise text
        # from the audio with local ASR, then cross-check it against source
        # captions when they exist. Disagreement means the segment is excluded.
        source_caption_path = media.get("caption_path")
        source_segments = _segments_from_vtt(source_caption_path) if source_caption_path else []

        generated_caption = directory / "generated.transcript.vtt"
        transcription_result = transcribe_media_to_vtt(
            media["media_path"],
            generated_caption,
            lesson["language"],
        )
        asr_segments = _segments_from_vtt(transcription_result["caption_path"])

        verification_mode = "asr_confidence"
        if source_segments:
            segments = verify_segments(source_segments, asr_segments)
            verification_mode = "source_plus_asr"
        else:
            segments = asr_segments

        if len(segments) < 5:
            raise RuntimeError(
                "No se detectaron suficientes frases cuya transcripción pudiera verificarse con confianza. "
                "Prueba con un vídeo con voz más clara o con mejores subtítulos."
            )

        exercises = generate_exercises(
            segments,
            lesson["difficulty"],
            lesson["max_items"],
        )
        if len(exercises) < 5:
            raise RuntimeError("No se pudieron generar suficientes ejercicios de calidad.")

        transcription = {
            key: value
            for key, value in transcription_result.items()
            if key != "caption_path"
        }
        transcription.update({
            "verification_mode": verification_mode,
            "source_segment_count": len(source_segments),
            "asr_segment_count": len(asr_segments),
            "verified_segment_count": len(segments),
        })

        lesson.update({
            "status": "ready",
            "title": media["title"],
            "video_id": media["video_id"],
            "platform": media.get("platform") or "web",
            "duration": media["duration"],
            "thumbnail": media["thumbnail"],
            "source_url": media["webpage_url"],
            "media_path": media["media_path"],
            "caption_path": transcription_result["caption_path"],
            "caption_source": "faster-whisper",
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
