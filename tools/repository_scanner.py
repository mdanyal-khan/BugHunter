"""TOOL-001 Repository Scanner — builds a structural map of the workspace."""
from __future__ import annotations

import os
import re

from security.workspace import Workspace

LANGUAGE_EXTENSIONS = {
    "Python": (".py",),
    "Dart": (".dart",),
    "JavaScript/TypeScript": (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"),
    "Go": (".go",),
    "Rust": (".rs",),
}
PYTHON_TEST_RE = re.compile(r"(?:^test_.*\.py$|_test\.py$)")
DART_TEST_RE = re.compile(r"_test\.dart$")
JS_TEST_RE = re.compile(r"\.(?:test|spec)\.(?:js|jsx|mjs|cjs|ts|tsx)$")
RUST_TEST_RE = re.compile(r"#\s*\[\s*(?:tokio::)?test\s*\]")


def scan(workspace: Workspace) -> dict:
    tree = workspace.file_tree()
    directories = []
    for dirpath, dirnames, _ in os.walk(workspace.root):
        dirnames[:] = [name for name in dirnames if name not in (
            ".git", "__pycache__", "venv", ".venv", "node_modules", ".dart_tool", "build", "target", "dist"
        )]
        for name in dirnames:
            directories.append(os.path.relpath(os.path.join(dirpath, name), workspace.root))
    language_counts = {
        language: sum(path.lower().endswith(extensions) for path in tree)
        for language, extensions in LANGUAGE_EXTENSIONS.items()
    }
    language_counts = {language: count for language, count in language_counts.items() if count}
    test_files = [
        path for path in tree
        if PYTHON_TEST_RE.search(os.path.basename(path))
        or DART_TEST_RE.search(os.path.basename(path))
        or JS_TEST_RE.search(os.path.basename(path))
        or os.path.basename(path).endswith("_test.go")
    ]
    if os.path.isfile(workspace.resolve("Cargo.toml")):
        for path in tree:
            if path.endswith(".rs") and _contains_rust_tests(workspace.resolve(path)):
                test_files.append(path)
    framework_names = []
    if any(path.endswith(".py") for path in test_files):
        framework_names.append("pytest / Python")
    pubspec_path = workspace.resolve("pubspec.yaml")
    if any(path.endswith(".dart") for path in test_files):
        if os.path.isfile(pubspec_path):
            with open(pubspec_path, encoding="utf-8", errors="replace") as pubspec:
                pubspec_text = pubspec.read()
            framework_names.append("Flutter" if re.search(r"(?m)^\s*(?:flutter|flutter_test)\s*:", pubspec_text)
                                  else "Dart")
        else:
            framework_names.append("Dart")
    if any(JS_TEST_RE.search(os.path.basename(path)) for path in test_files):
        framework_names.append("Node.js")
    if any(path.endswith("_test.go") for path in test_files):
        framework_names.append("Go")
    if any(path.endswith(".rs") for path in test_files):
        framework_names.append("Rust")
    return {
        "file_count": len(tree),
        "directories": sorted(directories),
        "python_file_count": language_counts.get("Python", 0),
        "language_counts": language_counts,
        "languages": list(language_counts),
        "files": tree,
        "test_files": test_files,
        "detected_framework": ", ".join(framework_names) or "none-detected",
    }


def _contains_rust_tests(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as source:
            return bool(RUST_TEST_RE.search(source.read()))
    except OSError:
        return False
