import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from app.api_client import fetch_status, APIError


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_successful_response_returns_status():
    def fake_get(url):
        return FakeResponse(200, {"status": "ok"})

    assert fetch_status("http://example.test/health", http_get=fake_get) == "ok"


def test_http_error_response_raises_api_error():
    def fake_get(url):
        return FakeResponse(404, {"error": "not found"})

    raised = None
    try:
        fetch_status("http://example.test/health", http_get=fake_get)
    except Exception as e:  # noqa: BLE001
        raised = e
    assert isinstance(raised, APIError), f"expected APIError, got {raised!r}"


def test_connection_error_raises_api_error():
    def fake_get(url):
        raise requests.exceptions.ConnectionError("simulated network failure")

    raised = None
    try:
        fetch_status("http://example.test/health", http_get=fake_get)
    except Exception as e:  # noqa: BLE001
        raised = e
    assert isinstance(raised, APIError), f"expected APIError, got {raised!r}"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASSED: {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAILED: {t.__name__}: {e}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
