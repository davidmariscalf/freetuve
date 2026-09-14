import html
import re
from dataclasses import dataclass


TIMESTAMP = re.compile(
    r"(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})"
)
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
NOISE = re.compile(r"^\s*[\[(].{0,60}[\])]\s*$")
END_PUNCT = re.compile(r"[.!?…][\"'”’)]?$", re.UNICODE)
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _seconds(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_caption_text(value: str) -> str:
    value = TAG.sub("", value)
    value = html.unescape(value).replace("\u00a0", " ")
    return SPACE.sub(" ", value).strip()


def parse_vtt(text: str) -> list[Cue]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[Cue] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("NOTE"):
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        match = TIMESTAMP.search(line)
        if not match:
            i += 1
            continue
        start = _seconds(match.group("start"))
        end = _seconds(match.group("end"))
        i += 1
        body: list[str] = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i].strip())
            i += 1
        caption = clean_caption_text(" ".join(body))
        if caption and end > start:
            if not cues or cues[-1].text != caption or abs(cues[-1].start - start) > 0.05:
                cues.append(Cue(start=start, end=end, text=caption))
    return cues


def _word_count(text: str) -> int:
    return len(WORD.findall(text))


def _merge_text(left: str, right: str) -> str:
    if not left:
        return right
    left_norm = left.casefold()
    right_norm = right.casefold()
    if right_norm.startswith(left_norm):
        return right
    if left_norm.startswith(right_norm):
        return left

    left_words = left.split()
    right_words = right.split()
    max_overlap = min(8, len(left_words), len(right_words))
    for size in range(max_overlap, 0, -1):
        if [w.casefold() for w in left_words[-size:]] == [w.casefold() for w in right_words[:size]]:
            return " ".join(left_words + right_words[size:])
    return f"{left} {right}".strip()


def build_segments(cues: list[Cue]) -> list[dict]:
    segments: list[dict] = []
    current_text = ""
    start = 0.0
    end = 0.0
    previous_end = 0.0

    def flush() -> None:
        nonlocal current_text, start, end
        text = SPACE.sub(" ", current_text).strip()
        duration = end - start
        words = _word_count(text)
        if 1.0 <= duration <= 14.0 and 3 <= words <= 20 and not NOISE.match(text):
            if not segments or segments[-1]["text"].casefold() != text.casefold():
                segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        current_text = ""
        start = 0.0
        end = 0.0

    for cue in cues:
        text = cue.text.strip()
        if not text or NOISE.match(text) or text in {"♪", "♫"}:
            continue
        if current_text and cue.start - previous_end > 1.8:
            flush()
        if not current_text:
            start = cue.start
            current_text = text
        else:
            current_text = _merge_text(current_text, text)
        end = max(end, cue.end)
        previous_end = cue.end

        words = _word_count(current_text)
        duration = end - start
        if (END_PUNCT.search(current_text) and words >= 3) or words >= 12 or duration >= 8.0:
            flush()

    if current_text:
        flush()
    return segments
