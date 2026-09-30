from pathlib import Path

from security.workspace import Workspace
from tools.code_search import find_symbol
from tools.dependency_inspector import inspect_dependencies


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