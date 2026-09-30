"""TOOL-001 Repository Scanner — builds a structural map of the workspace."""
from __future__ import annotations

import os

from security.workspace import Workspace

TEST_MARKERS = ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")


def scan(workspace: Workspace) -> dict:
    tree = workspace.file_tree()
    directories = []
    for dirpath, dirnames, _ in os.walk(workspace.root):
        dirnames[:] = [name for name in dirnames if name not in (".git", "__pycache__", "venv", ".venv")]
        for name in dirnames:
            directories.append(os.path.relpath(os.path.join(dirpath, name), workspace.root))
    py_files = [f for f in tree if f.endswith(".py")]
    test_files = [f for f in py_files if os.path.basename(f).startswith("test_") or f.endswith("_test.py")]
    has_pytest_config = any(os.path.exists(workspace.resolve(m)) for m in TEST_MARKERS)
    return {
        "file_count": len(tree),
        "directories": sorted(directories),
        "python_file_count": len(py_files),
        "files": tree,
        "test_files": test_files,
        "detected_framework": "pytest" if (test_files or has_pytest_config) else "none-detected",
    }
