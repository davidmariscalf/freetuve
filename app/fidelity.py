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


def align_manual_transcript(
    manual_transcript: str,
    asr_segments: list[dict],
    *,
    minimum_similarity: float = 0.65,
    max_ahead_tokens: int = 180,
) -> list[dict]:
    """Align user supplied transcript text to ASR timed segments.

    Whisper remains the timing source. The manual transcript only supplies
    wording for segments that can be matched confidently in sequence, so a
    pasted transcript never invents timestamps or silently drifts away from
    the audio.
    """
    manual_tokens = [match.group(0) for match in WORD.finditer(manual_transcript)]
    manual_norm = [token.casefold().replace("’", "'") for token in manual_tokens]
    if not manual_tokens or not asr_segments:
        return []

    aligned: list[dict] = []
    cursor = 0

    for segment in asr_segments:
        target = _tokens(str(segment.get("text") or ""))
        if len(target) < 2:
            continue

        min_size = max(2, len(target) - 2)
        max_size = min(len(manual_tokens), len(target) + 3)
        if min_size > max_size:
            continue

        search_start = max(0, cursor - 2)
        search_end = min(
            len(manual_tokens),
            max(search_start + max_ahead_tokens, cursor + len(target) * 8),
        )

        best_score = 0.0
        best_start = -1
        best_end = -1
        for start in range(search_start, search_end):
            for size in range(min_size, max_size + 1):
                end = start + size
                if end > search_end:
                    break
                score = SequenceMatcher(None, target, manual_norm[start:end]).ratio()
                if score > best_score:
                    best_score = score
                    best_start = start
                    best_end = end

        if best_score < minimum_similarity or best_start < 0:
            continue

        item = dict(segment)
        item["text"] = " ".join(manual_tokens[best_start:best_end])
        item["manual_similarity"] = round(best_score, 4)
        aligned.append(item)
        cursor = best_end

    return aligned
