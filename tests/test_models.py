from app.models import LessonCreate


def test_lesson_create_accepts_adaptive_exercise_count():
    payload = LessonCreate(
        url="https://example.com/video",
        language="en",
        difficulty="medium",
        max_items=0,
    )

    assert payload.max_items == 0


def test_lesson_create_defaults_to_video_mode():
    payload = LessonCreate(url="https://example.com/video")
    assert payload.source_type == "video"


def test_lesson_create_accepts_movie_mode():
    payload = LessonCreate(url="https://example.com/movie", source_type="movie")
    assert payload.source_type == "movie"
