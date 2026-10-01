"""
Configuration loading (AI-004): all provider credentials and model names are
read from environment variables (optionally via a local .env file) and are
never hard-coded. The Streamlit sidebar may override provider/model choice
and iteration/timeout limits for the current session only (FR-023) — it
never writes secrets back to disk (SEC-008, DATA-005).
"""
from __future__ import annotations

import os


def _load_dotenv_if_present(path: str = ".env") -> None:
    """Minimal .env loader (avoids a hard dependency on python-dotenv)."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv_if_present()


class Config:
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_BASE: str = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")

    HF_API_KEY: str = os.environ.get("HF_API_KEY", "")
    HF_MODEL: str = os.environ.get("HF_MODEL", "openai/gpt-oss-120b:fastest")
    HF_API_BASE: str = os.environ.get("HF_API_BASE", "https://api-inference.huggingface.co")

    DEFAULT_PROVIDER: str = os.environ.get("DEFAULT_PROVIDER", "groq")

    MAX_ITERATIONS_DEFAULT: int = int(os.environ.get("BUGHUNTER_MAX_ITERATIONS", "5"))
    TIMEOUT_SECONDS_DEFAULT: int = int(os.environ.get("BUGHUNTER_TIMEOUT_SECONDS", "60"))
    LLM_TIMEOUT_SECONDS: int = int(os.environ.get("BUGHUNTER_LLM_TIMEOUT", "30"))
    MAX_UPLOAD_MB: int = int(os.environ.get("BUGHUNTER_MAX_UPLOAD_MB", "25"))
    MAX_AGENT_STEPS_PER_ITERATION: int = int(os.environ.get("BUGHUNTER_MAX_STEPS", "4"))

    WORKSPACE_ROOT: str = os.environ.get("BUGHUNTER_WORKSPACE_ROOT", "/tmp/bughunter_workspaces")
    REPORTS_DIR: str = os.environ.get("BUGHUNTER_REPORTS_DIR", "./reports")

    @classmethod
    def has_key(cls, provider: str) -> bool:
        if provider == "groq":
            return bool(cls.GROQ_API_KEY)
        if provider == "huggingface":
            return bool(cls.HF_API_KEY)
        if provider == "mock":
            return True
        return False
