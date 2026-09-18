from types import SimpleNamespace

from app.main import _CREATE_EVENTS, _client_rate_key, _prune_create_events


def _request(headers=None, host="100.64.0.2"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=host),
    )


def test_uses_railway_real_client_ip_for_rate_limit_key():
    request = _request({"x-real-ip": "203.0.113.42"})
    assert _client_rate_key(request) == "203.0.113.42"


def test_invalid_real_ip_falls_back_to_socket_client():
    request = _request({"x-real-ip": "not-an-ip"}, host="100.64.0.9")
    assert _client_rate_key(request) == "100.64.0.9"


def test_ipv6_is_normalized():
    request = _request({"x-real-ip": "2001:db8::0001"})
    assert _client_rate_key(request) == "2001:db8::1"

def test_public_direct_client_cannot_spoof_real_ip_header():
    request = _request({"x-real-ip": "1.2.3.4"}, host="8.8.8.8")
    assert _client_rate_key(request) == "8.8.8.8"



def test_prune_create_events_removes_only_inactive_clients():
    _CREATE_EVENTS.clear()
    _CREATE_EVENTS["stale"].extend([100.0, 200.0])
    _CREATE_EVENTS["mixed"].extend([100.0, 900.0])
    _CREATE_EVENTS["fresh"].extend([950.0])

    _prune_create_events(800.0)

    assert "stale" not in _CREATE_EVENTS
    assert list(_CREATE_EVENTS["mixed"]) == [900.0]
    assert list(_CREATE_EVENTS["fresh"]) == [950.0]
    _CREATE_EVENTS.clear()
