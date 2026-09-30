"""TOOL-006 Test Discovery and TOOL-007 Test Runner."""
from __future__ import annotations

import os
import re
import sys

from core.models import TestResult as RunResult
from security.command_policy import run_allowlisted
from security.workspace import Workspace

SUMMARY_RE = re.compile(r"(\d+) passed")
FAILED_RE = re.compile(r"(\d+) failed")
ERROR_RE = re.compile(r"(\d+) error")


def discover_tests(workspace: Workspace) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(workspace.root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "venv", ".venv")]
        for fn in filenames:
            if fn.startswith("test_") and fn.endswith(".py"):
                found.append(os.path.relpath(os.path.join(dirpath, fn), workspace.root))
    return sorted(found)


def run_tests(workspace: Workspace, target: str = None, timeout: int = 60) -> TestResult:
    """Runs pytest if available, otherwise falls back to the demo repos' own
    self-runner convention (`python <test_file>.py`), so the MVP still works
    in environments where pytest is not installed (PERF-003, SYS-006)."""
    test_targets = [target] if target else discover_tests(workspace)

    if not test_targets:
        return RunResult(command="(none)", passed=False, status="NO_TESTS",
                           output="No test files were found in this repository.")

    # Attempt 1: pytest (the expected/standard path per SYS-006).
    cmd = [sys.executable, "-m", "pytest", "-q", *test_targets]
    result = run_allowlisted(cmd, cwd=workspace.root, timeout=timeout)
    pytest_missing = "No module named pytest" in (result.stderr or "")
    if not pytest_missing:
        return _from_pytest(cmd, result, test_targets)

    # Attempt 2: fallback self-runner (each test file executed directly).
    return _run_fallback(workspace, test_targets, timeout)


def _from_pytest(cmd, result, test_targets) -> TestResult:
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


def _run_fallback(workspace: Workspace, test_targets, timeout) -> TestResult:
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
        m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
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
