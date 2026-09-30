"""
MockProvider — a scripted, deterministic stand-in for a real LLM provider.

This is NOT one of the two required providers (Groq/Hugging Face, AI-002/
AI-003); it is an additional, clearly-labeled "Offline Demo" option that lets
BugHunter Agent run its full Observe-Reason-Act-Test loop end to end with no
API key and no internet connection — useful for rehearsing a hackathon demo
on unreliable venue Wi-Fi, and for automated self-tests of the rest of the
pipeline. It recognizes the three bundled demo repositories (Section 30 of
the SRS) by filename and walks through the same JSON "agent step" contract
a real provider would produce. For any other repository it honestly reports
that it has no scripted fix, rather than fabricating one.
"""
from __future__ import annotations

import json
import difflib
import os

from providers.base import LLMProvider

FIXED_USERS_PY = '''"""A tiny in-memory user directory used for Demo Bug 1 (None handling)."""

USERS = {
    1: {"name": "Ada Lovelace"},
    2: {"name": "Grace Hopper"},
}


def find_user(user_id):
    """Returns the user dict for user_id, or None if not found."""
    return USERS.get(user_id)


def get_user_name(user_id):
    """Returns the uppercase display name for a user, or "UNKNOWN"."""
    user = find_user(user_id)
    if user is None:
        return "UNKNOWN"
    return user["name"].upper()
'''

FIXED_PRICING_PY = '''"""Pricing helpers used for Demo Bug 2 (incorrect business logic)."""


def apply_discount(price, percent):
    """Applies a percentage discount to a price."""
    return price - (price * percent / 100)
'''

FIXED_API_CLIENT_PY = '''"""A tiny API client used for Demo Bug 3 (unhandled API exceptions)."""
import requests


class APIError(Exception):
    """Raised when the remote API cannot be reached or returns an error."""


def fetch_status(url, http_get=None):
    """Fetches {"status": ...} from url and returns the status value."""
    http_get = http_get or requests.get
    try:
        response = http_get(url)
    except requests.exceptions.RequestException as e:
        raise APIError(f"Network error while calling {url}: {e}") from e
    if response.status_code != 200:
        raise APIError(f"API returned HTTP {response.status_code} for {url}")
    try:
        return response.json()["status"]
    except (KeyError, ValueError) as e:
        raise APIError(f"Malformed response from {url}: {e}") from e
'''

# A plausible-but-wrong first attempt for Demo Bug 2, so the offline demo visibly
# exercises the failed-test -> revert -> re-investigate feedback loop (FR-015).
WRONG_FIRST_PRICING_PY = '''"""Pricing helpers used for Demo Bug 2 (incorrect business logic)."""


def apply_discount(price, percent):
    """Applies a percentage discount to a price."""
    return price - (price * percent / 10)
'''

# filename -> (search keyword, symbol keyword, fixed file content, hypothesis, summary)
PLAYBOOKS = {
    "app/users.py": (
        "find_user", "get_user_name", FIXED_USERS_PY,
        "get_user_name() indexes into the result of find_user() without checking for None, "
        "so an unknown user_id raises an unhandled error instead of degrading gracefully.",
        "Return \"UNKNOWN\" when find_user() cannot locate the requested user.",
    ),
    "app/pricing.py": (
        "apply_discount", "apply_discount", FIXED_PRICING_PY,
        "apply_discount() treats the percent argument as an already-normalized fraction instead of "
        "dividing by 100, so discounts are applied 100x too large.",
        "Divide percent by 100 before applying the discount.",
    ),
    "app/api_client.py": (
        "fetch_status", "fetch_status", FIXED_API_CLIENT_PY,
        "fetch_status() does not catch connection errors or check the HTTP status code, so failures "
        "surface as raw, unclear exceptions instead of the existing APIError type.",
        "Wrap the request in error handling and raise APIError for both HTTP and connection failures.",
    ),
}


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, api_key: str = None, model: str = None):
        self.model = "mock-scripted-v1"
        self.workspace = None  # attached by AgentController before use
        self.call_count = 0
        self.patch_attempts = 0

    def health_check(self) -> bool:
        return True

    def chat(self, messages: list, json_mode: bool = False, max_tokens: int = 1200) -> str:
        step = self.call_count % 3
        self.call_count += 1

        target = self._detect_target_file()
        if target is None:
            return json.dumps({
                "thought": "I don't recognize this repository's structure well enough to propose a "
                           "confident fix in offline demo mode.",
                "hypothesis": "Unknown — offline demo mode only recognizes the three bundled demo repositories.",
                "action": "finish_no_fix",
                "action_input": {"reason": "No scripted playbook matches this repository. Configure a real "
                                            "Groq or Hugging Face API key for general-purpose reasoning."},
                "next_action_hint": "Switch to Groq or Hugging Face in the sidebar for real repositories.",
            })

        search_kw, symbol, fixed_content, hypothesis, summary = PLAYBOOKS[target]

        if step == 0:
            return json.dumps({
                "thought": f"The bug report suggests the issue is in code related to '{search_kw}'. Searching.",
                "hypothesis": hypothesis,
                "action": "search",
                "action_input": {"query": search_kw},
                "next_action_hint": f"Read the file that defines {symbol}.",
            })
        if step == 1:
            return json.dumps({
                "thought": f"Found {symbol} in {target}. Reading the full file for context.",
                "hypothesis": hypothesis,
                "action": "read_file",
                "action_input": {"path": target},
                "next_action_hint": "Generate a patch.",
            })

        self.patch_attempts += 1
        if target == "app/pricing.py" and self.patch_attempts == 1:
            fixed_content = WRONG_FIRST_PRICING_PY
            summary = "Scale the percentage down before applying the discount."
        diff = self._compute_diff(target, fixed_content)
        return json.dumps({
            "thought": "I have enough context to propose a fix.",
            "hypothesis": hypothesis,
            "action": "generate_patch",
            "action_input": {"diff": diff, "summary": summary, "files_changed": [target]},
            "next_action_hint": "Apply the patch and run the tests.",
        })

    # ------------------------------------------------------------------ #
    def _detect_target_file(self):
        if not self.workspace:
            return None
        tree = {path.replace("\\", "/") for path in self.workspace.file_tree()}
        for candidate in PLAYBOOKS:
            if candidate in tree:
                return candidate
        return None

    def _compute_diff(self, relative_path: str, new_content: str) -> str:
        """Build a unified diff without modifying the workspace file."""
        full = os.path.join(self.workspace.root, relative_path)
        with open(full, "r", encoding="utf-8", newline="") as f:
            original = f.read()
        return "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        ))
