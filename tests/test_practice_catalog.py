from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prebuilt_catalog_covers_all_cefr_levels():
    source = (ROOT / "frontend" / "practice-catalog.js").read_text(encoding="utf-8")

    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert f"level: '{level}'" in source

    assert source.count("practice({") >= 18
    for language in ("'en'", "'es'", "'fr'"):
        assert f"language: {language}" in source


def test_catalog_is_loaded_before_main_app_and_is_locally_graded():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert index.index("/practice-catalog.js?v=1") < index.index("/app.js?v=9")
    assert "let catalogMode = false" in app
    assert "SpeechSynthesisUtterance" in app
    assert "catalogMode = Boolean(lesson?.catalog)" in app
    assert "offlineMode = isOffline || catalogMode" in app


def test_catalog_contains_no_streaming_service_media_urls():
    source = (ROOT / "frontend" / "practice-catalog.js").read_text(encoding="utf-8").lower()

    assert "netflix.com" not in source
    assert "tmdb" not in source
    assert "media_url" not in source
