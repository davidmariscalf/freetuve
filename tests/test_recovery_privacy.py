from pathlib import Path


def test_pending_recovery_payload_is_session_scoped_and_legacy_local_data_is_purged():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "recovery.js").read_text(encoding="utf-8")

    assert "sessionStorage.getItem(pendingKey(id))" in source
    assert "sessionStorage.setItem(pendingKey(id)" in source
    assert "sessionStorage.removeItem(pendingKey(id))" in source
    assert "purgeLegacyPendingRequests()" in source
    assert "localStorage.removeItem(key)" in source
    assert "localStorage.setItem(pendingKey(id)" not in source


def test_recovery_preserves_movie_mode_status_copy():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "recovery.js").read_text(encoding="utf-8")

    assert "pollLessonWithRecovery(initialId, kind = 'video')" in source
    assert "kind === 'movie' ? 'película' : 'vídeo'" in source
    assert "Procesando ${noun}, subtítulos y ejercicios…" in source
    assert "kind === 'movie' ? 9600 : 1200" in source
    assert "Prueba con una fuente más corta o ligera." in source
