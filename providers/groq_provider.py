"""
GroqProvider — primary LLM provider, selected for fast inference (AI-002).
Uses Groq's OpenAI-compatible /chat/completions endpoint over plain HTTPS
so the app has no hard dependency on the `groq` SDK.
"""
from __future__ import annotations

import time

import requests

from core.config import Config
from providers.base import LLMProvider, ProviderError, ChatMessage


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or Config.GROQ_API_KEY
        self.model = model or Config.GROQ_MODEL
        self.base_url = Config.GROQ_API_BASE

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def chat(self, messages: list, json_mode: bool = False, max_tokens: int = 1200) -> str:
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not configured.", kind="auth")

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_err = None
        for attempt in range(3):  # AI-005: bounded retries with backoff
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=Config.LLM_TIMEOUT_SECONDS,
                )
            except requests.exceptions.Timeout:
                last_err = ProviderError("Groq request timed out.", kind="timeout")
                time.sleep(1.5 * (attempt + 1))
                continue
            except requests.exceptions.RequestException as e:
                last_err = ProviderError(f"Network error contacting Groq: {e}", kind="network")
                time.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code == 429:
                last_err = ProviderError("Groq rate limit reached.", kind="rate_limit")
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code == 401:
                raise ProviderError("Groq rejected the API key (401 Unauthorized).", kind="auth")
            if resp.status_code >= 500:
                last_err = ProviderError(f"Groq server error ({resp.status_code}).", kind="server")
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code != 200:
                raise ProviderError(f"Groq returned HTTP {resp.status_code}: {resp.text[:300]}", kind="error")

            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise ProviderError(f"Unexpected Groq response shape: {data}", kind="error")

        raise last_err or ProviderError("Groq request failed after retries.", kind="error")

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            self.chat([ChatMessage(role="user", content="ping")], max_tokens=5)
            return True
        except ProviderError:
            return False
