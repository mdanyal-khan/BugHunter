import os

from security.command_policy import CommandResult
from tools.test_runner import _from_native_runner, _from_pytest, discover_tests, run_tests


def test_pytest_collection_error_is_classified_as_error():
    result = CommandResult(
        ok=False,
        returncode=2,
        stdout="",
        stderr="ERROR collecting test_module.py\n1 error in 0.03s",
        duration_ms=30,
    )

    test_result = _from_pytest(["python", "-m", "pytest"], result, ["test_module.py"])

    assert test_result.status == "ERROR"
    assert test_result.failed_count == 1


def test_pytest_assertion_failure_remains_fail():
    result = CommandResult(
        ok=False,
        returncode=1,
        stdout="1 failed in 0.03s",
        stderr="",
        duration_ms=30,
    )

    test_result = _from_pytest(["python", "-m", "pytest"], result, ["test_module.py"])

    assert test_result.status == "FAIL"


def test_discovery_finds_multiple_language_test_files(tmp_path):
    for path in ("test_core.py", "test/widget_test.dart", "src/math.test.js", "pkg/math_test.go"):
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("", encoding="utf-8")

    class TestWorkspace:
        root = str(tmp_path)

    assert discover_tests(TestWorkspace()) == sorted([
        os.path.join("pkg", "math_test.go"),
        os.path.join("src", "math.test.js"),
        "test_core.py",
        os.path.join("test", "widget_test.dart"),
    ])


def test_flutter_project_selects_flutter_test_command(tmp_path):
    from tools.test_runner import _test_commands

    (tmp_path / "pubspec.yaml").write_text("dev_dependencies:\n  flutter_test:\n", encoding="utf-8")

    class TestWorkspace:
        root = str(tmp_path)

        @staticmethod
        def resolve(path):
            return str(tmp_path / path)

    assert _test_commands(TestWorkspace(), ["test/widget_test.dart"]) == [
        ("dart", ["flutter", "test"])
    ]


def test_native_runner_failure_is_reported():
    result = CommandResult(False, 1, "# fail 2", "", 45)

    test_result = _from_native_runner(["node", "--test"], result)

    assert test_result.status == "FAIL"
    assert test_result.failed_count == 2


def test_missing_sdk_returns_actionable_error(tmp_path, monkeypatch):
    from tools import test_runner

    class TestWorkspace:
        root = str(tmp_path)

        @staticmethod
        def resolve(path):
            return str(tmp_path / path)

    (tmp_path / "pubspec.yaml").write_text("dev_dependencies:\n  flutter_test:\n", encoding="utf-8")
    monkeypatch.setattr(test_runner, "discover_tests", lambda workspace: ["test/widget_test.dart"])
    monkeypatch.setattr(test_runner.shutil, "which", lambda tool: None)

    result = run_tests(TestWorkspace())

    assert result.status == "ERROR"
    assert "flutter" in result.output


def test_target_cannot_escape_the_workspace(tmp_path, monkeypatch):
    from core.config import Config
    from security.workspace import Workspace
    from tools import test_runner

    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    def unexpected_run(*args, **kwargs):
        raise AssertionError("escaped target must not execute")

    monkeypatch.setattr(test_runner, "run_allowlisted", unexpected_run)
    try:
        result = run_tests(workspace, "../outside_test.py")

        assert result.status == "ERROR"
        assert "outside" in result.output
    finally:
        workspace.destroy()