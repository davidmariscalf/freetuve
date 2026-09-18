from pathlib import Path


def test_pending_recovery_payload_is_session_scoped_and_legacy_local_data_is_purged():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "recovery.js").read_text(encoding="utf-8")

    assert "sessionStorage.getItem(pendingKey(id))" in source
    assert "sessionStorage.setItem(pendingKey(id)" in source
    assert "sessionStorage.removeItem(pendingKey(id))" in source
    assert "purgeLegacyPendingRequests()" in source
    assert "localStorage.removeItem(key)" in source
    assert "localStorage.setItem(pendingKey(id)" not in source
