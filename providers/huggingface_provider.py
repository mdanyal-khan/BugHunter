"""
HuggingFaceProvider — alternative LLM provider (AI-003). Uses the HF
router's OpenAI-compatible chat-completions endpoint over plain HTTPS,
so no hard dependency on `huggingface_hub` is required.
"""
from __future__ import annotations

import time

import requests

from core.config import Config
from providers.base import LLMProvider, ProviderError


class HuggingFaceProvider(LLMProvider):
    name = "huggingface"

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or Config.HF_API_KEY
        self.model = model or Config.HF_MODEL
        # HF's OpenAI-compatible router; falls back gracefully if the account/model
        # does not support it (surfaced to the user as a clear ProviderError).
        self.base_url = "https://router.huggingface.co/v1"

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def chat(self, messages: list, json_mode: bool = False, max_tokens: int = 1200) -> str:
        if not self.api_key:
            raise ProviderError("HF_API_KEY is not configured.", kind="auth")

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=Config.LLM_TIMEOUT_SECONDS,
                )
            except requests.exceptions.Timeout:
                last_err = ProviderError("Hugging Face request timed out.", kind="timeout")
                time.sleep(1.5 * (attempt + 1))
                continue
            except requests.exceptions.RequestException as e:
                last_err = ProviderError(f"Network error contacting Hugging Face: {e}", kind="network")
                time.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code == 429:
                last_err = ProviderError("Hugging Face rate limit reached.", kind="rate_limit")
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code == 401:
                raise ProviderError("Hugging Face rejected the API token (401).", kind="auth")
            if resp.status_code >= 500:
                last_err = ProviderError(f"Hugging Face server error ({resp.status_code}).", kind="server")
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code != 200:
                raise ProviderError(f"Hugging Face returned HTTP {resp.status_code}: {resp.text[:300]}", kind="error")

            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise ProviderError(f"Unexpected Hugging Face response shape: {data}", kind="error")

        raise last_err or ProviderError("Hugging Face request failed after retries.", kind="error")

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        from providers.base import ChatMessage
        try:
            self.chat([ChatMessage(role="user", content="ping")], max_tokens=5)
            return True
        except ProviderError:
            return False
