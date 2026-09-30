import json

from agent.controller import AgentController, _redact_tool_output
from core.config import Config
from core.models import BugReport, Investigation, Patch, PatchStatus, TestResult as RunResult
from security.workspace import Workspace


class OneStepProvider:
    name = "test"

    def __init__(self, response):
        self.response = response

    def chat(self, messages, json_mode=False, max_tokens=1200):
        return json.dumps(self.response)

    def health_check(self):
        return True


def test_no_tests_keeps_patch_applied_and_unverified(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    provider = OneStepProvider({
        "action": "generate_patch",
        "action_input": {"diff": "unused diff", "summary": "candidate fix"},
        "hypothesis": "The reported defect has a localized cause.",
        "thought": "private internal reasoning must not be shown",
    })
    patch = Patch(diff="candidate diff", summary="candidate fix", status=PatchStatus.APPLIED)
    monkeypatch.setattr("agent.controller.patch_tools.validate_and_apply", lambda *args: patch)
    monkeypatch.setattr("agent.controller.test_runner.run_tests", lambda *args, **kwargs: RunResult(
        command="(none)", status="NO_TESTS", output="No test files were found."))
    try:
        investigation = Investigation(bug_report=BugReport(description="Check this bug"), max_iterations=1)
        events = list(AgentController(workspace, provider, investigation).run())

        assert events[-1]["outcome"] == "HUMAN_INTERVENTION"
        assert patch.status == PatchStatus.APPLIED
        assert "unverified" in investigation.final_report.summary.lower()
        report = investigation.final_report.to_markdown(investigation)
        assert "No test files were found." in report
        assert "(none)" in report
        assert "candidate diff" in report
        assert all("private internal reasoning" not in str(event) for event in events)
    finally:
        workspace.destroy()


def test_activity_reason_does_not_expose_model_thought(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))
    workspace = Workspace()
    provider = OneStepProvider({
        "action": "finish_no_fix",
        "action_input": {"reason": "Not enough evidence"},
        "thought": "private internal reasoning must not be shown",
    })
    try:
        investigation = Investigation(bug_report=BugReport(description="Check this bug"), max_iterations=1)
        events = list(AgentController(workspace, provider, investigation).run())
        step = next(event for event in events if event["type"] == "step")

        assert "reason" in step
        assert "thought" not in step
        assert "private internal reasoning" not in investigation.iterations[0].reason
        assert "private internal reasoning" not in investigation.final_report.to_markdown(investigation)
    finally:
        workspace.destroy()


def test_tool_output_redacts_and_counts_secret_patterns():
    secret = "gsk_" + "A" * 30

    output, count = _redact_tool_output(f'api_key="{secret}"')

    assert secret not in output
    assert "REDACTED-SECRET" in output
    assert count >= 1