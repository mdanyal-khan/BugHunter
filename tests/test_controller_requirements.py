import json
import pytest

from agent.controller import AgentController, _redact_tool_output
from core.config import Config
from core.models import BugReport, Investigation, Patch, PatchStatus, TestResult as RunResult
from providers.base import ProviderError
from security.workspace import Workspace


class OneStepProvider:
    name = "test"

    def __init__(self, response):
        self.response = response

    def chat(self, messages, json_mode=False, max_tokens=1200):
        return json.dumps(self.response)

    def health_check(self):
        return True


def test_invalid_patch_notice_includes_redacted_validation_reason(monkeypatch, tmp_path):
    from agent import controller as controller_module

    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(Config, "MAX_AGENT_STEPS_PER_ITERATION", 2)
    workspace = Workspace()
    provider = OneStepProvider({
        "action": "generate_patch",
        "action_input": {"diff": "invalid diff", "summary": "candidate fix"},
    })
    invalid_patch = Patch(
        diff="invalid diff",
        summary='candidate fix\n\n[Validation failed]\nerror: No valid patches in input (allow with "--allow-empty")',
        status=PatchStatus.INVALID,
    )
    monkeypatch.setattr(controller_module.patch_tools, "validate_and_apply", lambda *args: invalid_patch)
    try:
        investigation = Investigation(bug_report=BugReport(description="Check this bug"), max_iterations=1)
        events = list(AgentController(workspace, provider, investigation).run())
        notices = [event for event in events if event["type"] == "notice" and event.get("details")]
        notice = notices[0]

        assert "valid unified diff" in notice["details"]
        assert "No valid patches in input" not in notice["details"]
        assert notice["retrying"] is True
        assert notices[-1]["retrying"] is False
        assert "candidate fix" not in notice["details"]
    finally:
        workspace.destroy()


class FailoverProvider:
    def __init__(self, name, result=None, error=None):
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    def chat(self, *args, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_controller_switches_from_groq_to_hugging_face(monkeypatch):
    from agent import controller as controller_module

    monkeypatch.setattr(controller_module.prompts, "build_messages", lambda context: [])
    groq = FailoverProvider("groq", error=ProviderError("quota reached", kind="rate_limit"))
    huggingface = FailoverProvider("huggingface", result='{"action":"finish_no_fix"}')
    controller = AgentController.__new__(AgentController)
    controller.provider = groq
    controller.fallback = huggingface

    step, notice = controller._ask_llm({})

    assert step["action"] == "finish_no_fix"
    assert notice == "Groq unavailable; continuing with Hugging Face."
    assert (groq.calls, huggingface.calls) == (1, 1)


def test_controller_switches_back_to_groq_when_hugging_face_is_limited(monkeypatch):
    from agent import controller as controller_module

    monkeypatch.setattr(controller_module.prompts, "build_messages", lambda context: [])
    huggingface = FailoverProvider("huggingface", error=ProviderError("quota reached", kind="rate_limit"))
    groq = FailoverProvider("groq", result='{"action":"finish_no_fix"}')
    controller = AgentController.__new__(AgentController)
    controller.provider = huggingface
    controller.fallback = groq

    step, notice = controller._ask_llm({})

    assert step["action"] == "finish_no_fix"
    assert notice == "Hugging Face unavailable; continuing with Groq."
    assert (huggingface.calls, groq.calls) == (1, 1)


def test_controller_reports_and_records_hugging_face_model_fallback(monkeypatch):
    from types import SimpleNamespace

    from agent import controller as controller_module
    from providers.huggingface_provider import FALLBACK_MODEL

    monkeypatch.setattr(controller_module.prompts, "build_messages", lambda context: [])
    huggingface = FailoverProvider("huggingface", result='{"action":"finish_no_fix"}')
    huggingface.model = "meta-llama/Llama-3.2-1B-Instruct"

    def switch_model(*args, **kwargs):
        huggingface.model = FALLBACK_MODEL
        return huggingface.result

    huggingface.chat = switch_model
    controller = AgentController.__new__(AgentController)
    controller.provider = huggingface
    controller.fallback = None
    controller.inv = SimpleNamespace(model_name="meta-llama/Llama-3.2-1B-Instruct")

    step, notice = controller._ask_llm({})

    assert step["action"] == "finish_no_fix"
    assert "switched to " + FALLBACK_MODEL in notice
    assert controller.inv.model_name == FALLBACK_MODEL


def test_controller_explains_when_both_providers_are_limited(monkeypatch):
    from agent import controller as controller_module

    monkeypatch.setattr(controller_module.prompts, "build_messages", lambda context: [])
    groq = FailoverProvider("groq", error=ProviderError("rate limit", kind="rate_limit"))
    huggingface = FailoverProvider("huggingface", error=ProviderError("quota", kind="rate_limit"))
    controller = AgentController.__new__(AgentController)
    controller.provider = groq
    controller.fallback = huggingface

    with pytest.raises(ProviderError) as error:
        controller._ask_llm({})

    assert error.value.kind == "provider_failover"
    assert "Groq" in str(error.value)
    assert "Hugging Face" in str(error.value)
    assert "retry after the rate limits reset" in str(error.value)


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