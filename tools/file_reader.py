"""TOOL-002 File Reader and TOOL-005 Dependency Inspector."""
from __future__ import annotations

import os

from security.workspace import Workspace, WorkspaceSecurityError

MAX_READ_BYTES = 40_000
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pyc", ".so", ".exe", ".pdf"}


def read_file(workspace: Workspace, relative_path: str, start_line: int = None, end_line: int = None) -> dict:
    """Reads a file's contents (optionally a line range). Never raises out of the sandbox."""
    try:
        full = workspace.resolve(relative_path)
    except WorkspaceSecurityError as e:
        return {"ok": False, "error": str(e)}

    if not os.path.isfile(full):
        return {"ok": False, "error": f"File not found: {relative_path}"}
    if os.path.splitext(full)[1].lower() in BINARY_EXTENSIONS:
        return {"ok": False, "error": "Refusing to read a binary file."}
    if os.path.getsize(full) > MAX_READ_BYTES:
        return {"ok": False, "error": f"File exceeds the {MAX_READ_BYTES}-byte read limit."}

    with open(full, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if start_line or end_line:
        s = max((start_line or 1) - 1, 0)
        e = end_line or len(lines)
        content = "".join(lines[s:e])
    else:
        content = "".join(lines)

    return {"ok": True, "path": relative_path, "content": content, "total_lines": len(lines)}


def inspect_dependencies(workspace: Workspace) -> dict:
    manifests = ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
    for m in manifests:
        full = workspace.resolve(m)
        if os.path.isfile(full):
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            deps = []
            if m == "requirements.txt":
                deps = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.startswith("#")]
            return {"manifest": m, "raw": content[:4000], "dependencies": deps}
    return {"manifest": None, "raw": "", "dependencies": []}
