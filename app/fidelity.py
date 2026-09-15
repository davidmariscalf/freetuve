import re
from difflib import SequenceMatcher


WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold().replace("’", "'") for match in WORD.finditer(text)]


def _window_similarity(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a

    # Caption and ASR segment boundaries rarely match exactly. Compare the
    # shorter token sequence against nearby windows of the longer sequence so
    # boundary differences do not look like transcription disagreements.
    best = 0.0
    minimum = max(1, len(a) - 2)
    maximum = min(len(b), len(a) + 2)
    for size in range(minimum, maximum + 1):
        for start in range(0, len(b) - size + 1):
            score = SequenceMatcher(None, a, b[start:start + size]).ratio()
            best = max(best, score)
    return best


def verify_segments(
    source_segments: list[dict],
    asr_segments: list[dict],
    *,
    minimum_similarity: float = 0.68,
    padding_seconds: float = 0.8,
) -> list[dict]:
    """Keep ASR segments only when independent source captions support them.

    The returned text always comes from the local ASR transcript. Source
    captions are used only as an independent consistency check. This prevents
    an inaccurate automatic caption from becoming the exercise answer while
    still rejecting ASR segments where the two systems materially disagree.
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
