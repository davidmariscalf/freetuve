from pathlib import Path


def test_cross_origin_offline_clips_are_intercepted_before_origin_guard():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "sw.js").read_text(encoding="utf-8")

    clip_guard = "OFFLINE_CLIP_PATH.test(url.pathname)"
    origin_guard = "url.origin !== self.location.origin"

    assert clip_guard in source
    assert origin_guard in source
    assert source.index(clip_guard) < source.index(origin_guard)
    assert "freetuve-shell-v12" in source
    assert "/practice-catalog.js?v=1" in source
