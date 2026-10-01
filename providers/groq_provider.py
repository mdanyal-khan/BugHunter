"""
GroqProvider — primary LLM provider, selected for fast inference (AI-002).
Uses Groq's OpenAI-compatible /chat/completions endpoint over plain HTTPS
so the app has no hard dependency on the `groq` SDK.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

from core.config import Config
from providers.base import LLMProvider, ProviderError, ChatMessage

MAX_ATTEMPTS = 4
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h)")


def _parse_wait_seconds(value: str) -> Optional[float]:
    value = value.strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        pass

    parts = _DURATION_PART.findall(value.lower())
    if not parts or "".join(amount + unit for amount, unit in parts) != value.lower():
        return None
    factors = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(amount) * factors[unit] for amount, unit in parts)


def _rate_limit_wait(response, attempt: int) -> float:
    headers = response.headers
    waits = [
        _parse_wait_seconds(headers.get(name, ""))
        for name in (
            "Retry-After",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
        )
    ]
    provider_waits = [wait for wait in waits if wait is not None]
    return max(provider_waits) if provider_waits else min(30.0, 2.0 ** (attempt + 1))


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
        json_fallback_used = False
        for attempt in range(MAX_ATTEMPTS):
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
                wait_seconds = _rate_limit_wait(resp, attempt)
                raise ProviderError(
                    f"Groq rate limit or quota reached; retry after {wait_seconds:g}s.", kind="rate_limit"
                )
            if resp.status_code == 401:
                raise ProviderError("Groq rejected the API key (401 Unauthorized).", kind="auth")
            if resp.status_code >= 500:
                last_err = ProviderError(f"Groq server error ({resp.status_code}).", kind="server")
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 400 and json_mode and not json_fallback_used:
                try:
                    error_code = resp.json().get("error", {}).get("code")
                except (AttributeError, ValueError):
                    error_code = None
                if error_code == "json_validate_failed":
                    payload.pop("response_format", None)
                    json_fallback_used = True
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
