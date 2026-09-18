import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_index_has_no_inline_javascript():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    script_tags = re.findall(r"<script(?:\s[^>]*)?>", html, flags=re.IGNORECASE)
    assert script_tags
    assert all(" src=" in tag for tag in script_tags)


def test_netlify_enforces_script_csp_and_clickjacking_protection():
    config = (ROOT / "netlify.toml").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in config
    assert "script-src 'self'" in config
    assert "object-src 'none'" in config
    assert "frame-ancestors 'none'" in config
    assert 'X-Frame-Options = "DENY"' in config
