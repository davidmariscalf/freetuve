from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_voice_waits_for_async_browser_voices():
    source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "async function availableSpeechVoices()" in source
    assert "voiceschanged" in source
    assert "setTimeout(done, 1200)" in source


def test_catalog_voice_requires_exact_locale_instead_of_first_language_match():
    source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "normalizeSpeechLocale(voice.lang) === targetLocale" in source
    assert "bestCatalogSpeechVoice(utterance.lang)" in source
    assert ".startsWith(prefix)" not in source


def test_catalog_voice_prefers_higher_quality_exact_locale_engines():
    source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "natural|neural|premium|enhanced" in source
    assert "google|microsoft|apple" in source
    assert "espeak|festival|compact" in source
