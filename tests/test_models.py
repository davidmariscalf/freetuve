from app.models import LessonCreate


def test_lesson_create_accepts_adaptive_exercise_count():
    payload = LessonCreate(
        url="https://example.com/video",
        language="en",
        difficulty="medium",
        max_items=0,
    )

    assert payload.max_items == 0
