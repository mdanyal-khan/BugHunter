"""
Core data models for BugHunter Agent.

These dataclasses mirror the logical data model in the SRS (Section 24):
BugReport, Investigation, AgentIteration, ToolExecution, Patch, TestRun,
TestResult, FinalReport. They are held in memory / session state for the
MVP (see DATA-001) and can be serialized to JSON for the optional report
export described in DATA-002.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class InvestigationStatus(str, Enum):
    IDLE = "IDLE"
    REPOSITORY_LOADED = "REPOSITORY_LOADED"
    ANALYZING = "ANALYZING"
    INVESTIGATING = "INVESTIGATING"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    PATCH_APPLIED = "PATCH_APPLIED"
    TESTING = "TESTING"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"
    ANALYZING_FAILURE = "ANALYZING_FAILURE"
    COMPLETED = "COMPLETED"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    HUMAN_INTERVENTION = "HUMAN_INTERVENTION"
    UNRECOVERABLE_ERROR = "UNRECOVERABLE_ERROR"


class PatchStatus(str, Enum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVERTED = "reverted"
    INVALID = "invalid"


@dataclass
class ToolExecution:
    id: str = field(default_factory=new_id)
    tool_name: str = ""
    input: str = ""
    output: str = ""
    ok: bool = True
    timestamp: float = field(default_factory=time.time)


@dataclass
class TestResult:
    id: str = field(default_factory=new_id)
    command: str = ""
    passed: bool = False
    status: str = "UNKNOWN"  # PASS | FAIL | ERROR | TIMEOUT | NO_TESTS
    duration_ms: int = 0
    output: str = ""
    passed_count: int = 0
    failed_count: int = 0


@dataclass
class Patch:
    id: str = field(default_factory=new_id)
    diff: str = ""
    summary: str = ""
    files_changed: list = field(default_factory=list)
    status: PatchStatus = PatchStatus.PROPOSED
    checkpoint_ref: Optional[str] = None  # git commit sha before this patch


@dataclass
class AgentIteration:
    id: str = field(default_factory=new_id)
    iteration_no: int = 0
    hypothesis: str = ""
    action: str = ""
    reason: str = ""
    files_inspected: list = field(default_factory=list)
    tool_executions: list = field(default_factory=list)  # list[ToolExecution]
    patch: Optional[Patch] = None
    test_result: Optional[TestResult] = None
    next_action: str = ""


@dataclass
class BugReport:
    id: str = field(default_factory=new_id)
    description: str = ""
    stack_trace: str = ""
    submitted_at: float = field(default_factory=time.time)


@dataclass
class FinalReport:
    id: str = field(default_factory=new_id)
    outcome: str = ""  # COMPLETED | MAX_ITERATIONS | HUMAN_INTERVENTION | UNRECOVERABLE_ERROR
    iterations_used: int = 0
    accepted_patch: Optional[Patch] = None
    summary: str = ""
    generated_at: float = field(default_factory=time.time)

    def to_markdown(self, investigation: "Investigation") -> str:
        lines = [
            f"# BugHunter Agent — Final Report",
            "",
            f"**Outcome:** {self.outcome}",
            f"**Iterations used:** {self.iterations_used} / {investigation.max_iterations}",
            f"**Provider:** {investigation.provider_name} ({investigation.model_name})",
            "",
            "## Bug Report",
            f"> {investigation.bug_report.description}",
        ]
        if investigation.bug_report.stack_trace:
            lines += ["", "**Stack trace:**", "```", investigation.bug_report.stack_trace, "```"]
        lines += ["", "## Summary", self.summary, "", "## Iteration History"]
        for it in investigation.iterations:
            lines.append(f"### Iteration {it.iteration_no}")
            lines.append(f"- **Hypothesis:** {it.hypothesis or '—'}")
            lines.append(f"- **Action:** {it.action or '—'}")
            if it.files_inspected:
                lines.append(f"- **Files inspected:** {', '.join(it.files_inspected)}")
            if it.patch:
                lines.append(f"- **Patch status:** {it.patch.status.value}")
            if it.test_result:
                lines.append(f"- **Test result:** {it.test_result.status} "
                              f"({it.test_result.passed_count} passed / {it.test_result.failed_count} failed)")
            lines.append("")
        if self.accepted_patch:
            lines += ["## Accepted Patch", "```diff", self.accepted_patch.diff, "```"]
        else:
            lines += ["## Accepted Patch", "_No patch was approved as final for this session._"]
        return "\n".join(lines)


@dataclass
class Investigation:
    id: str = field(default_factory=new_id)
    bug_report: BugReport = field(default_factory=BugReport)
    provider_name: str = "groq"
    model_name: str = ""
    status: InvestigationStatus = InvestigationStatus.IDLE
    max_iterations: int = 5
    timeout_seconds: int = 60
    iterations: list = field(default_factory=list)  # list[AgentIteration]
    final_report: Optional[FinalReport] = None
    workspace_path: str = ""

    def to_dict(self) -> dict:
        """Recursively convert to a plain, JSON-serializable dict (Enums -> their value)."""
        return _to_jsonable(self)


def _to_jsonable(obj):
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_jsonable(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj
