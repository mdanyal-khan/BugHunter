"""TOOL-003 Code Search and TOOL-004 Symbol Search."""
from __future__ import annotations

import os
import re

from security.workspace import Workspace

MAX_RESULTS = 25
SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}


def search(workspace: Workspace, query: str, file_types=(".py",)) -> list:
    """Case-insensitive substring search across text files (TOOL-003)."""
    results = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if file_types and not fn.endswith(file_types):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, workspace.root)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append({"file": rel, "line": lineno, "text": line.strip()[:160]})
                            if len(results) >= MAX_RESULTS:
                                return results
            except OSError:
                continue
    return results


_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")
_CLASS_RE = re.compile(r"^\s*class\s+(\w+)\s*[:\(]")


def find_symbol(workspace: Workspace, symbol: str) -> list:
    """Finds definitions of a function/class name (TOOL-004)."""
    results = []
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, workspace.root)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        m = _DEF_RE.match(line) or _CLASS_RE.match(line)
                        if m and m.group(1) == symbol:
                            results.append({"file": rel, "line": lineno, "text": line.strip()})
            except OSError:
                continue
            if len(results) >= MAX_RESULTS:
                return results
    return results
