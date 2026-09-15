import random
import re
import unicodedata
from difflib import SequenceMatcher


WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
MARKER = "[[blank:{index}]]"
STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "been", "being", "could", "does", "doing",
    "from", "have", "here", "into", "just", "like", "more", "most", "much", "only", "other", "really",
    "some", "than", "that", "their", "them", "then", "there", "these", "they", "this", "those", "through",
    "very", "want", "were", "what", "when", "where", "which", "while", "with", "would", "your",
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("’", "'")
    value = re.sub(r"[^\w'\-]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _word_matches(text: str):
    return list(WORD.finditer(text))


def _candidate_indices(text: str) -> list[int]:
    matches = _word_matches(text)
    good = [
        i for i, match in enumerate(matches)
        if len(match.group(0)) >= 4 and match.group(0).casefold() not in STOPWORDS
    ]
    return good or [i for i, match in enumerate(matches) if len(match.group(0)) >= 3]


def _mask(text: str, selected: list[int]) -> tuple[str, list[str]]:
    matches = _word_matches(text)
    selected = sorted(set(selected))
    expected = [matches[i].group(0) for i in selected]
    replacements = [
        (matches[word_index].start(), matches[word_index].end(), MARKER.format(index=blank_index))
        for blank_index, word_index in enumerate(selected)
    ]
    result = text
    for start, end, marker in reversed(replacements):
        result = result[:start] + marker + result[end:]
    return result, expected


def _distractors(target: str, corpus: list[str], rng: random.Random) -> list[str]:
    unique = []
    seen = {target.casefold()}
    for word in sorted(corpus, key=lambda w: (abs(len(w) - len(target)), w.casefold())):
        key = word.casefold()
        if key not in seen and len(word) >= 2:
            seen.add(key)
            unique.append(word)
        if len(unique) >= 8:
            break
    rng.shuffle(unique)
    options = [target] + unique[:3]
    rng.shuffle(options)
    return options


def _kind_for(index: int, difficulty: str) -> str:
    if difficulty == "easy":
        return "multiple_choice" if index % 2 == 0 else "cloze"
    if difficulty == "medium":
        return "multiple_choice" if index % 3 == 0 else "cloze"
    if difficulty == "hard":
        return "dictation" if index % 3 == 2 else "cloze"
    return "dictation" if index % 4 != 0 else "cloze"


def generate_exercises(segments: list[dict], difficulty: str, max_items: int) -> list[dict]:
    corpus = [m.group(0) for segment in segments for m in _word_matches(segment["text"])]
    exercises: list[dict] = []

    for segment_index, segment in enumerate(segments):
        if len(exercises) >= max_items:
            break
        text = segment["text"]
        candidates = _candidate_indices(text)
        if not candidates:
            continue

        exercise_index = len(exercises)
        rng = random.Random(f"{difficulty}|{segment_index}|{text}")
        kind = _kind_for(exercise_index, difficulty)
        exercise = {
            "id": f"ex-{exercise_index + 1}",
            "start": segment["start"],
            "end": segment["end"],
            "type": kind,
            "min_listens": 2,
            "transcript": text,
        }

        if kind == "dictation":
            exercise.update({
                "display": "Escribe exactamente la frase que escuchas.",
                "blank_count": 0,
                "choices": [],
                "expected": text,
            })
        else:
            blank_count = 1
            if kind == "cloze":
                desired = {"easy": 1, "medium": 2, "hard": 3, "expert": 4}.get(difficulty, 2)
                blank_count = min(desired, max(1, len(candidates) // 2), len(candidates))
            selected = sorted(rng.sample(candidates, blank_count))
            display, expected = _mask(text, selected)
            choices = _distractors(expected[0], corpus, rng) if kind == "multiple_choice" else []
            exercise.update({
                "display": display,
                "blank_count": blank_count,
                "choices": choices,
                "expected": expected,
            })
        exercises.append(exercise)

    return exercises


def score_answer(exercise: dict, answer: str | list[str], listens: int) -> dict:
    expected = exercise["expected"]
    kind = exercise["type"]
    replay_penalty = max(0, listens - exercise.get("min_listens", 2)) * 4

    if kind == "dictation":
        supplied = answer if isinstance(answer, str) else " ".join(answer)
        similarity = SequenceMatcher(None, _normalize(str(expected)), _normalize(supplied)).ratio()
        accuracy = round(similarity, 4)
        correct = similarity >= 0.96
        score = max(0, round(similarity * 100) - replay_penalty)
        correct_answer: str | list[str] = str(expected)
    else:
        expected_list = [str(item) for item in expected]
        supplied_list = [answer] if isinstance(answer, str) else answer
        pairs = zip(expected_list, supplied_list)
        matches = sum(
            1
            for target, supplied in pairs
            if _normalize(target) == _normalize(str(supplied))
        )
        accuracy = matches / max(1, len(expected_list))
        correct = len(supplied_list) == len(expected_list) and accuracy == 1.0
        score = max(0, round(accuracy * 100) - replay_penalty)
        correct_answer = expected_list

    return {
        "correct": correct,
        "accuracy": accuracy,
        "score": score,
        "correct_answer": correct_answer,
        "transcript": exercise.get("transcript", ""),
    }
