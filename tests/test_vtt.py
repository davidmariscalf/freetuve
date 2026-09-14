from app.vtt import build_segments, parse_vtt


def test_parse_and_group_webvtt():
    raw = """WEBVTT

00:00:01.000 --> 00:00:02.600
I have been

00:00:02.600 --> 00:00:04.400
I have been living here for three years.

00:00:05.000 --> 00:00:06.500
[Music]

00:00:07.000 --> 00:00:09.000
What are you doing today?
"""
    cues = parse_vtt(raw)
    assert len(cues) == 4
    segments = build_segments(cues)
    assert segments[0]["text"] == "I have been living here for three years."
    assert segments[1]["text"] == "What are you doing today?"
    assert segments[0]["start"] == 1.0


def test_html_tags_are_removed():
    raw = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c.colorE5E5E5>Hello <b>there</b>, my friend.</c>
"""
    cues = parse_vtt(raw)
    assert cues[0].text == "Hello there, my friend."
