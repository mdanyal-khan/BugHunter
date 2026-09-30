"""TOOL-003 Code Search and TOOL-004 Symbol Search."""
from __future__ import annotations

import ast
import os
import re

from security.workspace import Workspace, WorkspaceSecurityError

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
                with open(workspace.resolve(rel), "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append({"file": rel, "line": lineno, "text": line.strip()[:160]})
                            if len(results) >= MAX_RESULTS:
                                return results
            except (OSError, WorkspaceSecurityError):
                continue
    return results


_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")
_CLASS_RE = re.compile(r"^\s*class\s+(\w+)\s*[:\(]")


def find_symbol(workspace: Workspace, symbol: str) -> list:
    """Find definitions and references to a Python symbol (TOOL-004)."""
    if not symbol:
        return []
    results = []
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, workspace.root)
            try:
                with open(workspace.resolve(rel), "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except (OSError, WorkspaceSecurityError):
                continue
            lines = source.splitlines()
            try:
                tree = ast.parse(source, filename=rel)
            except SyntaxError:
                tree = None
            if tree is not None:
                for node in ast.walk(tree):
                    kind = None
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
                        kind = "definition"
                    elif isinstance(node, ast.Name) and node.id == symbol:
                        kind = "reference"
                    elif isinstance(node, ast.Attribute) and node.attr == symbol:
                        kind = "reference"
                    elif isinstance(node, ast.alias) and (node.asname or node.name.rsplit(".", 1)[-1]) == symbol:
                        kind = "reference"
                    if kind and node.lineno <= len(lines):
                        results.append({"file": rel, "line": node.lineno,
                                        "text": lines[node.lineno - 1].strip()[:160], "kind": kind})
                        if len(results) >= MAX_RESULTS:
                            return results
            else:
                for lineno, line in enumerate(lines, start=1):
                    if re.search(rf"\b{re.escape(symbol)}\b", line):
                        match = _DEF_RE.match(line) or _CLASS_RE.match(line)
                        kind = "definition" if match and match.group(1) == symbol else "reference"
                        results.append({"file": rel, "line": lineno,
                                        "text": line.strip()[:160], "kind": kind})
                        if len(results) >= MAX_RESULTS:
                            return results
    if not results:
        for hit in search(workspace, symbol):
            hit["kind"] = "text match"
            results.append(hit)
            if len(results) >= MAX_RESULTS:
                break
    return sorted(results, key=lambda hit: (hit["file"], hit["line"]))
