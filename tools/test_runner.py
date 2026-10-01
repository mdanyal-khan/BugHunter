"""TOOL-006 Test Discovery and TOOL-007 Test Runner."""
from __future__ import annotations

import os
import re
import shutil
import sys

from core.models import TestResult as RunResult
from security.command_policy import run_allowlisted
from security.workspace import Workspace
from security.workspace import WorkspaceSecurityError
from tools.repository_scanner import DART_TEST_RE, JS_TEST_RE, PYTHON_TEST_RE
from tools.repository_scanner import RUST_TEST_RE

SUMMARY_RE = re.compile(r"(\d+) passed")
FAILED_RE = re.compile(r"(\d+) failed")
ERROR_RE = re.compile(r"(\d+) error")


def discover_tests(workspace: Workspace) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        dirnames[:] = [d for d in dirnames if d not in (
            ".git", "__pycache__", "venv", ".venv", "node_modules", ".dart_tool", "build", "target", "dist"
        )]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if (PYTHON_TEST_RE.search(fn) or DART_TEST_RE.search(fn) or JS_TEST_RE.search(fn)
                    or fn.endswith("_test.go")
                    or (fn.endswith(".rs") and _is_rust_test(workspace, path))):
                found.append(os.path.relpath(path, workspace.root))
    return sorted(found)


def run_tests(workspace: Workspace, target: str = None, timeout: int = 60) -> RunResult:
    """Run detected Python, Dart/Flutter, Node.js, Go, and Rust test suites."""
    if target:
        try:
            resolved_target = workspace.resolve(target)
        except WorkspaceSecurityError:
            return RunResult(command="(blocked)", passed=False, status="ERROR",
                             output="The requested test target is outside the isolated workspace.", failed_count=1)
        if not os.path.isfile(resolved_target):
            return RunResult(command="(invalid target)", passed=False, status="ERROR",
                             output="The requested test target does not exist in the isolated workspace.", failed_count=1)
        test_targets = [os.path.relpath(resolved_target, workspace.root)]
    else:
        test_targets = discover_tests(workspace)

    if not test_targets:
        return RunResult(command="(none)", passed=False, status="NO_TESTS",
                           output="No test files were found in this repository.")

    suites = _test_commands(workspace, test_targets)
    if not suites:
        return RunResult(command="(none)", passed=False, status="NO_TESTS",
                         output="No supported test runner could be selected for the discovered test files.")

    results = []
    for label, cmd in suites:
        required_tool = cmd[0]
        if required_tool not in (sys.executable, "python", "python3") and not shutil.which(required_tool):
            results.append(RunResult(
                command=" ".join(cmd), passed=False, status="ERROR",
                output=f"Required test tool '{required_tool}' is not installed or not on PATH.",
                failed_count=1,
            ))
            continue
        result = run_allowlisted(cmd, cwd=workspace.root, timeout=timeout)
        if label == "python" and "No module named pytest" in (result.stderr or ""):
            python_tests = [path for path in test_targets if path.endswith(".py")]
            results.append(_run_python_fallback(workspace, python_tests, timeout))
        elif label == "python":
            results.append(_from_pytest(cmd, result, test_targets))
        else:
            results.append(_from_native_runner(cmd, result))

    return _combine_results(results)


def _test_commands(workspace: Workspace, test_targets: list) -> list:
    suites = []
    python_tests = [path for path in test_targets if path.endswith(".py")]
    dart_tests = [path for path in test_targets if path.endswith(".dart")]
    js_tests = [path for path in test_targets if JS_TEST_RE.search(os.path.basename(path))]
    go_tests = [path for path in test_targets if path.endswith("_test.go")]
    rust_sources = [path for path in test_targets if path.endswith(".rs")]

    if python_tests:
        suites.append(("python", [sys.executable, "-m", "pytest", "-q", *python_tests]))
    if dart_tests:
        pubspec = workspace.resolve("pubspec.yaml")
        if os.path.isfile(pubspec):
            with open(pubspec, encoding="utf-8", errors="replace") as manifest:
                is_flutter = bool(re.search(r"(?m)^\s*(?:flutter|flutter_test)\s*:", manifest.read()))
        else:
            is_flutter = False
        tool = "flutter" if is_flutter else "dart"
        suites.append(("dart", [tool, "test"]))
    if js_tests:
        package_json = workspace.resolve("package.json")
        has_npm_test = False
        if os.path.isfile(package_json):
            try:
                import json
                with open(package_json, encoding="utf-8") as manifest:
                    has_npm_test = bool(json.load(manifest).get("scripts", {}).get("test"))
            except (OSError, ValueError, AttributeError):
                pass
        suites.append(("node", ["npm", "test"] if has_npm_test else ["node", "--test", *js_tests]))
    if go_tests:
        suites.append(("go", ["go", "test", "-v", "./..."]))
    if rust_sources and os.path.isfile(workspace.resolve("Cargo.toml")):
        suites.append(("rust", ["cargo", "test"]))
    return suites


def _is_rust_test(workspace: Workspace, path: str) -> bool:
    if not os.path.isfile(workspace.resolve("Cargo.toml")):
        return False
    if os.path.basename(os.path.dirname(path)) == "tests":
        return True
    try:
        with open(path, encoding="utf-8", errors="replace") as source:
            return bool(RUST_TEST_RE.search(source.read()))
    except OSError:
        return False


def _from_native_runner(cmd, result) -> RunResult:
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if result.timed_out:
        status = "TIMEOUT"
    elif result.ok:
        status = "PASS"
    else:
        status = "FAIL"
    passed_count = _count_matches(output, (
        r"(\d+) passed", r"# pass (\d+)", r"\+(\d+): all tests passed",
        r"test result: ok\.\s*(\d+) passed", r"--- PASS:", r"\bok\s+\S+\s+\([^)]+\)",
    )) if result.ok else 0
    failed_count = _count_matches(output, (
        r"(\d+) failed", r"# fail (\d+)", r"test result: .*?;\s*(\d+) failed", r"--- FAIL:"
    ))
    if not result.ok and failed_count == 0:
        failed_count = 1
    if result.ok and passed_count == 0:
        passed_count = 1
    return RunResult(command=" ".join(cmd), passed=result.ok, status=status,
                     duration_ms=result.duration_ms, output=output[-6000:],
                     passed_count=passed_count, failed_count=failed_count)


def _count_matches(output: str, patterns: tuple) -> int:
    for pattern in patterns:
        matches = re.findall(pattern, output, flags=re.IGNORECASE)
        if matches:
            return sum(int(match) if match.isdigit() else 1 for match in matches)
    return 0


def _combine_results(results: list) -> RunResult:
    priority = {"TIMEOUT": 4, "ERROR": 3, "FAIL": 2, "PASS": 1}
    status = max((result.status for result in results), key=lambda item: priority.get(item, 0))
    output = "\n\n".join(f"$ {result.command}\n{result.output}" for result in results)[-6000:]
    return RunResult(
        command="; ".join(result.command for result in results),
        passed=status == "PASS", status=status,
        duration_ms=sum(result.duration_ms for result in results), output=output,
        passed_count=sum(result.passed_count for result in results),
        failed_count=sum(result.failed_count for result in results),
    )


def _from_pytest(cmd, result, test_targets) -> RunResult:
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.timed_out:
        return RunResult(command=" ".join(cmd), passed=False, status="TIMEOUT",
                           duration_ms=result.duration_ms, output=output)
    passed_m = SUMMARY_RE.search(output)
    failed_m = FAILED_RE.search(output)
    error_m = ERROR_RE.search(output)
    passed_count = int(passed_m.group(1)) if passed_m else 0
    failed_count = (int(failed_m.group(1)) if failed_m else 0) + (int(error_m.group(1)) if error_m else 0)
    if result.ok and failed_count == 0:
        status = "PASS"
    elif error_m and not failed_m:
        status = "ERROR"
    elif not result.ok and not passed_m and not failed_m and not error_m:
        status = "ERROR"
    else:
        status = "FAIL"
    return RunResult(
        command=" ".join(cmd), passed=(status == "PASS"), status=status,
        duration_ms=result.duration_ms, output=output[-6000:],
        passed_count=passed_count, failed_count=failed_count,
    )


def _run_python_fallback(workspace: Workspace, test_targets, timeout) -> RunResult:
    combined_output = []
    total_passed = 0
    total_failed = 0
    any_timeout = False
    for t in test_targets:
        cmd = [sys.executable, t]
        result = run_allowlisted(cmd, cwd=workspace.root, timeout=timeout)
        combined_output.append(f"$ python {t}\n{result.stdout}\n{result.stderr}")
        if result.timed_out:
            any_timeout = True
            continue
        m = re.search(r"(\d+) passed, (\d+) failed", result.stdout or "")
        if m:
            total_passed += int(m.group(1))
            total_failed += int(m.group(2))
        elif not result.ok:
            total_failed += 1
    output = "\n\n".join(combined_output)[-6000:]
    if any_timeout:
        return RunResult(command="python <test files>", passed=False, status="TIMEOUT", output=output)
    status = "PASS" if total_failed == 0 and total_passed > 0 else "FAIL"
    return RunResult(
        command="python <test files> (pytest unavailable — used fallback runner)",
        passed=(status == "PASS"), status=status, output=output,
        passed_count=total_passed, failed_count=total_failed,
    )
