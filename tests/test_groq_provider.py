from types import SimpleNamespace

import pytest

from providers import groq_provider
from providers.base import ChatMessage, ProviderError
from providers.groq_provider import GroqProvider


class FakeResponse:
    def __init__(self, status_code, *, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload or {}
        self.text = str(self.payload)

    def json(self):
        return self.payload


def test_rate_limit_retry_waits_for_provider_reset(monkeypatch):
    responses = iter([
        FakeResponse(429, headers={
            "retry-after": "4",
            "x-ratelimit-reset-tokens": "9s",
        }),
        FakeResponse(200, payload={"choices": [{"message": {"content": "{}"}}]}),
    ])
    waits = []
    monkeypatch.setattr(groq_provider.requests, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(groq_provider.time, "sleep", waits.append)

    result = GroqProvider(api_key="test-key").chat(
        [ChatMessage(role="user", content="hello")], json_mode=True
    )

    assert result == "{}"
    assert waits == [9.0]


def test_repeated_rate_limits_use_bounded_backoff(monkeypatch):
    waits = []
    calls = []

    def rate_limited(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse(429)

    monkeypatch.setattr(groq_provider.requests, "post", rate_limited)
    monkeypatch.setattr(groq_provider.time, "sleep", waits.append)

    with pytest.raises(ProviderError) as error:
        GroqProvider(api_key="test-key").chat([ChatMessage(role="user", content="hello")])

    assert error.value.kind == "rate_limit"
    assert len(calls) == groq_provider.MAX_ATTEMPTS
    assert waits == [2.0, 4.0, 8.0]


def test_json_validation_error_retries_without_response_format(monkeypatch):
    responses = iter([
        FakeResponse(400, payload={"error": {"code": "json_validate_failed"}}),
        FakeResponse(200, payload={"choices": [{"message": {"content": "{}"}}]}),
    ])
    requests = []

    def fake_post(*args, **kwargs):
        requests.append(dict(kwargs["json"]))
        return next(responses)

    monkeypatch.setattr(groq_provider.requests, "post", fake_post)
    result = GroqProvider(api_key="test-key").chat(
        [ChatMessage(role="user", content="return JSON")], json_mode=True
    )

    assert result == "{}"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in requests[1]