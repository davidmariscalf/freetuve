import threading
from pathlib import Path

from .config import MAX_PROCESSING_ATTEMPTS
from .exercises import generate_exercises
from .fidelity import align_manual_transcript, verify_segments
from .heavy_media import download_media_and_captions
from .storage import lesson_dir, load_lesson, save_lesson
from .transcription import release_transcription_model, transcribe_media_to_vtt
from .vtt import build_segments, parse_vtt


_PROCESSING_LOCK = threading.Lock()


def _segments_from_vtt(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return build_segments(parse_vtt(text))


def _process_lesson_locked(lesson_id: str) -> None:
    try:
        lesson = load_lesson(lesson_id)
        if lesson.get("status") == "ready":
            return

        attempts = int(lesson.get("processing_attempts") or 0) + 1
        lesson["processing_attempts"] = attempts
        if attempts > MAX_PROCESSING_ATTEMPTS:
            lesson["status"] = "error"
            lesson["error"] = (
                "El procesamiento se detuvo porque este vídeo agotó repetidamente los recursos "
                "disponibles. Prueba con un vídeo más corto o ligero."
            )
            save_lesson(lesson)
            return

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
            duration_seconds=media.get("duration"),
        )
        asr_segments = _segments_from_vtt(transcription_result["caption_path"])

        verification_mode = "asr_confidence"
        manual_transcript = str(lesson.get("manual_transcript") or "").strip()
        manual_segments = (
            align_manual_transcript(manual_transcript, asr_segments)
            if manual_transcript
            else []
        )

        if manual_segments:
            # A manual transcript is user supplied reference text, not a timing
            # source. Keep Whisper timestamps and replace wording only where a
            # confident sequential match exists. Source captions can still
            # verify additional ASR segments that the manual text did not match.
            segments_by_time = {
                (round(float(item["start"]), 3), round(float(item["end"]), 3)): item
                for item in manual_segments
            }
            if source_segments:
                for item in verify_segments(source_segments, asr_segments):
                    key = (round(float(item["start"]), 3), round(float(item["end"]), 3))
                    segments_by_time.setdefault(key, item)
            segments = sorted(segments_by_time.values(), key=lambda item: float(item["start"]))
            verification_mode = "manual_plus_asr"
        elif source_segments:
            segments = verify_segments(source_segments, asr_segments)
            verification_mode = "source_plus_asr"
        else:
            segments = asr_segments

        if not segments:
            raise RuntimeError(
                "No se detectó ninguna frase cuya transcripción pudiera verificarse con suficiente confianza. "
                "Prueba con un vídeo con voz más clara o mejores subtítulos."
            )

        exercises = generate_exercises(
            segments,
            lesson["difficulty"],
            lesson["max_items"],
        )
        if not exercises:
            raise RuntimeError("No se pudo generar ningún ejercicio de calidad a partir de este vídeo.")

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
            "manual_transcript_used": bool(manual_segments),
            "manual_segment_count": len(manual_segments),
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
            "media_kind": media.get("media_kind") or "video",
            "media_bytes": media.get("media_bytes"),
            "download_profile": media.get("download_profile"),
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


def process_lesson(lesson_id: str) -> None:
    # A single heavy worker is deliberate. The Railway backend currently has a
    # 1 GB memory cap; overlapping yt-dlp/FFmpeg/Whisper jobs can cross that
    # limit even though each individual lesson fits comfortably.
    with _PROCESSING_LOCK:
        try:
            _process_lesson_locked(lesson_id)
        finally:
            # Do not keep the Whisper model resident between jobs. This restores
            # memory headroom for the web server and the next download.
            release_transcription_model()
