import re
from difflib import SequenceMatcher


WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold().replace("’", "'") for match in WORD.finditer(text)]


def _window_similarity(left: str, right: str) -> float:
    asr = _tokens(left)
    source = _tokens(right)
    if not asr or not source:
        return 0.0

    # The ASR sentence is the answer candidate. Compare it only against source
    # caption windows of almost the same length. Do not swap the sequences:
    # swapping can make a caption that omits several words look deceptively good.
    minimum = max(1, len(asr) - 1)
    maximum = min(len(source), len(asr) + 1)
    if minimum > maximum:
        return 0.0

    best = 0.0
    for size in range(minimum, maximum + 1):
        for start in range(0, len(source) - size + 1):
            score = SequenceMatcher(None, asr, source[start:start + size]).ratio()
            best = max(best, score)
    return best


def verify_segments(
    source_segments: list[dict],
    asr_segments: list[dict],
    *,
    minimum_similarity: float = 0.80,
    padding_seconds: float = 0.8,
) -> list[dict]:
    """Keep ASR segments only when independent source captions support them.

    The returned text always comes from the local ASR transcript. Source
    captions are used only as an independent consistency check. Exact-listening
    exercises prefer rejecting an ambiguous phrase over grading a learner
    against wording that the audio may not contain.
    """
    if not source_segments or not asr_segments:
        return []

    verified: list[dict] = []
    for segment in asr_segments:
        start = float(segment["start"])
        end = float(segment["end"])
        aligned = [
            candidate
            for candidate in source_segments
            if float(candidate["end"]) >= start - padding_seconds
            and float(candidate["start"]) <= end + padding_seconds
        ]
        if not aligned:
            continue

        source_text = " ".join(str(candidate["text"]) for candidate in aligned)
        similarity = _window_similarity(str(segment["text"]), source_text)
        if similarity < minimum_similarity:
            continue

        item = dict(segment)
        item["verification_similarity"] = round(similarity, 4)
        verified.append(item)

    return verified
