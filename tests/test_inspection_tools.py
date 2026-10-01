from pathlib import Path
import os

from security.workspace import Workspace
from tools.code_search import find_symbol
from tools.dependency_inspector import inspect_dependencies
from tools.repository_scanner import scan


def test_find_symbol_returns_definitions_and_references(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.Config.WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    try:
        Path(workspace.root, "sample.py").write_text(
            "def calculate(value):\n    return calculate_inner(value)\n\n"
            "def calculate_inner(value):\n    return value\n",
            encoding="utf-8",
        )
        matches = find_symbol(workspace, "calculate_inner")

        assert [(match["line"], match["kind"]) for match in matches] == [
            (2, "reference"), (4, "definition")
        ]
    finally:
        workspace.destroy()


def test_dependency_inspector_reads_requirements_and_pyproject(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.Config.WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    try:
        Path(workspace.root, "requirements.txt").write_text(
            "requests>=2.31\n# comment\npytest==8.0; python_version >= '3.10'\n",
            encoding="utf-8",
        )
        Path(workspace.root, "pyproject.toml").write_text(
            '[project]\ndependencies = ["flask>=3"]\n'
            '[project.optional-dependencies]\ntest = ["pytest>=7"]\n',
            encoding="utf-8",
        )

        result = inspect_dependencies(workspace)

        assert result["manifests"] == ["requirements.txt", "pyproject.toml"]
        assert [(item["name"], item["constraint"], item["group"]) for item in result["dependencies"]] == [
            ("requests", ">=2.31", "dependencies"),
            ("pytest", "==8.0; python_version >= '3.10'", "dependencies"),
            ("flask", ">=3", "dependencies"),
            ("pytest", ">=7", "test"),
        ]
    finally:
        workspace.destroy()


def test_repository_scan_reports_languages_and_frameworks(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.Config.WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    try:
        for path in ("lib/main.dart", "test/app_test.dart", "src/math.test.js", "app.py"):
            file_path = Path(workspace.root, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("", encoding="utf-8")
        Path(workspace.root, "pubspec.yaml").write_text("dev_dependencies:\n  flutter_test:\n", encoding="utf-8")

        result = scan(workspace)

        assert result["languages"] == ["Python", "Dart", "JavaScript/TypeScript"]
        assert result["language_counts"] == {"Python": 1, "Dart": 2, "JavaScript/TypeScript": 1}
        assert result["detected_framework"] == "Flutter, Node.js"
        assert len(result["test_files"]) == 2
    finally:
        workspace.destroy()


def test_repository_scan_detects_rust_unit_tests(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.Config.WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    try:
        Path(workspace.root, "Cargo.toml").write_text("[package]\nname='sample'\n", encoding="utf-8")
        source = Path(workspace.root, "src", "lib.rs")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("#[test]\nfn works() {}\n", encoding="utf-8")

        result = scan(workspace)

        assert result["languages"] == ["Rust"]
        assert result["test_files"] == [os.path.join("src", "lib.rs")]
        assert result["detected_framework"] == "Rust"
    finally:
        workspace.destroy()


def test_metrics_escape_untrusted_repository_labels(monkeypatch):
    from ui import components

    rendered = {}
    monkeypatch.setattr(components.st, "markdown", lambda content, **kwargs: rendered.update(content=content))

    components.metrics([("Repository", '<img src=x onerror="alert(1)">')])

    assert "&lt;img" in rendered["content"]
    assert "<img" not in rendered["content"]