from types import SimpleNamespace

from app.main import _client_rate_key


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

