from app.exercises import generate_exercises, score_answer


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


def test_skipped_segment_does_not_reduce_requested_count_when_more_are_available():
    unusable = {"start": 0.0, "end": 1.0, "text": "I am."}
    shifted = [
        {"start": item["start"] + 2.0, "end": item["end"] + 2.0, "text": item["text"]}
        for item in sample_segments()
    ]

    exercises = generate_exercises([unusable, *shifted], "medium", 5)

    assert len(exercises) == 5
    assert [item["id"] for item in exercises] == [f"ex-{index}" for index in range(1, 6)]
    assert all(item["transcript"] != "I am." for item in exercises)


def test_adaptive_count_uses_available_quality_segments_even_below_five():
    segments = sample_segments()[:3]

    exercises = generate_exercises(segments, "medium", 0)

    assert len(exercises) == 3
    assert [item["transcript"] for item in exercises] == [item["text"] for item in segments]


def test_requested_count_is_a_maximum_not_a_minimum():
    segments = sample_segments()[:2]

    exercises = generate_exercises(segments, "medium", 10)

    assert len(exercises) == 2


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


def test_easy_level_is_multiple_choice_with_three_options():
    exercises = generate_exercises(sample_segments(), "easy", 5)

    assert len(exercises) == 5
    assert all(item["type"] == "multiple_choice" for item in exercises)
    assert all(item["blank_count"] == 1 for item in exercises)
    assert all(len(item["choices"]) == 3 for item in exercises)


def test_medium_introduces_single_word_gap_fill_but_keeps_some_multiple_choice():
    exercises = generate_exercises(sample_segments(), "medium", 5)

    assert [item["type"] for item in exercises] == [
        "multiple_choice",
        "cloze",
        "cloze",
        "cloze",
        "multiple_choice",
    ]
    cloze = [item for item in exercises if item["type"] == "cloze"]
    assert cloze
    assert all(item["blank_count"] == 1 for item in cloze)


def test_hard_uses_multi_blank_cloze_and_some_dictation():
    exercises = generate_exercises(sample_segments(), "hard", 5)

    assert [item["type"] for item in exercises] == [
        "cloze",
        "cloze",
        "cloze",
        "dictation",
        "cloze",
    ]
    cloze = [item for item in exercises if item["type"] == "cloze"]
    assert all(item["blank_count"] >= 1 for item in cloze)
    assert any(item["blank_count"] == 2 for item in cloze)


def test_expert_is_mostly_dictation_with_harder_cloze():
    exercises = generate_exercises(sample_segments(), "expert", 5)

    assert [item["type"] for item in exercises] == [
        "cloze",
        "dictation",
        "dictation",
        "dictation",
        "cloze",
    ]
    assert sum(item["type"] == "dictation" for item in exercises) == 3
    assert any(
        item["blank_count"] >= 2
        for item in exercises
        if item["type"] == "cloze"
    )
