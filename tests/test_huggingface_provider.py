import pytest

from providers import huggingface_provider
from providers.base import ChatMessage, ProviderError
from providers.huggingface_provider import HuggingFaceProvider


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.headers = {}
        self.payload = payload or {}
        self.text = str(self.payload)

    def json(self):
        return self.payload


def test_rate_limit_returns_immediately_for_provider_failover(monkeypatch):
    calls = []
    waits = []

    def rate_limited(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse(429)

    monkeypatch.setattr(huggingface_provider.requests, "post", rate_limited)
    monkeypatch.setattr(huggingface_provider.time, "sleep", waits.append)

    with pytest.raises(ProviderError) as error:
        HuggingFaceProvider(api_key="test-token").chat([ChatMessage(role="user", content="hello")])

    assert error.value.kind == "rate_limit"
    assert "quota" in str(error.value).lower()
    assert len(calls) == 1
    assert waits == []


def test_unsupported_model_retries_with_provider_backed_fallback(monkeypatch):
    responses = iter([
        FakeResponse(400, {"error": {"code": "model_not_supported"}}),
        FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]}),
    ])
    requested_models = []

    def respond(*args, **kwargs):
        requested_models.append(kwargs["json"]["model"])
        return next(responses)

    monkeypatch.setattr(huggingface_provider.requests, "post", respond)
    provider = HuggingFaceProvider(api_key="test-token", model="meta-llama/Llama-3.2-1B-Instruct")

    result = provider.chat([ChatMessage(role="user", content="hello")], json_mode=True)

    assert result == "{}"
    assert requested_models == ["meta-llama/Llama-3.2-1B-Instruct", huggingface_provider.FALLBACK_MODEL]
    assert provider.model == huggingface_provider.FALLBACK_MODEL


def test_unsupported_fallback_model_has_actionable_error(monkeypatch):
    monkeypatch.setattr(
        huggingface_provider.requests, "post",
        lambda *args, **kwargs: FakeResponse(400, {"error": {"code": "model_not_supported"}}),
    )
    provider = HuggingFaceProvider(api_key="test-token", model=huggingface_provider.FALLBACK_MODEL)

    with pytest.raises(ProviderError) as error:
        provider.chat([ChatMessage(role="user", content="hello")])

    assert error.value.kind == "model_unavailable"
    assert "Enable an Inference Provider" in str(error.value)