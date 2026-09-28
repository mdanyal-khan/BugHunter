"""
LLMProvider — the abstract interface every AI provider must implement
(AI-001). The Agent Layer talks only to this interface, never to
provider-specific code (NFR-005).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Raised for auth, rate-limit, timeout, or server errors (AI-007)."""

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind  # "auth" | "rate_limit" | "timeout" | "server" | "network"


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def chat(self, messages: list, json_mode: bool = False, max_tokens: int = 1200) -> str:
        """Send a chat completion request and return the assistant's text content."""
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError
