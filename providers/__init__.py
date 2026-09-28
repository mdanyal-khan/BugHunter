"""Provider factory — the only place that maps a provider name to a class (AI-001, NFR-005)."""
from __future__ import annotations

from providers.base import LLMProvider, ProviderError, ChatMessage  # noqa: F401
from providers.groq_provider import GroqProvider
from providers.huggingface_provider import HuggingFaceProvider
from providers.mock_provider import MockProvider

PROVIDERS = {
    "groq": GroqProvider,
    "huggingface": HuggingFaceProvider,
    "mock": MockProvider,
}

PROVIDER_LABELS = {
    "groq": "Groq (fast inference)",
    "huggingface": "Hugging Face",
    "mock": "Offline Demo (no API key)",
}


def get_provider(name: str, api_key: str = None, model: str = None) -> LLMProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'.")
    return PROVIDERS[name](api_key=api_key, model=model)
