from security.command_policy import CommandResult
from tools.test_runner import _from_pytest


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