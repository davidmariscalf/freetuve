from app.exercises import generate_exercises, score_answer
from app.youtube import validate_youtube_url


def sample_segments():
    return [
        {"start": 0.0, "end": 3.0, "text": "I have been living here for three years."},
        {"start": 3.2, "end": 6.4, "text": "She really wants to learn another language."},
        {"start": 6.6, "end": 9.7, "text": "We are meeting our friends after school today."},
        {"start": 10.0, "end": 13.0, "text": "This exercise should become a useful listening challenge."},
        {"start": 13.2, "end": 16.5, "text": "Tomorrow they will travel together by train."},
    ]


def test_exercises_hide_words_and_have_answers():
    exercises = generate_exercises(sample_segments(), "medium", 5)
    assert len(exercises) == 5
    assert all(item["min_listens"] == 2 for item in exercises)
    assert any("[[blank:" in item["display"] for item in exercises if item["type"] != "dictation")
    assert all("expected" in item for item in exercises)
    assert all(item["transcript"] == sample_segments()[i]["text"] for i, item in enumerate(exercises))


def test_scoring_penalizes_extra_replays_and_reveals_transcript():
    exercise = {
        "type": "cloze",
        "expected": ["living"],
        "transcript": "I have been living here for three years.",
        "min_listens": 2,
    }
    perfect = score_answer(exercise, ["living"], 2)
    replayed = score_answer(exercise, ["living"], 4)
    assert perfect["correct"] is True
    assert perfect["score"] == 100
    assert perfect["transcript"] == exercise["transcript"]
    assert replayed["score"] < perfect["score"]


def test_youtube_url_validation():
    assert validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    try:
        validate_youtube_url("https://example.com/video")
    except ValueError:
        pass
    else:
        raise AssertionError("Non YouTube host should be rejected")
