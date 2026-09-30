"""
Agent Controller (Agent Layer) — orchestrates the
Observe -> Reason -> Act -> Test -> Observe Again loop (FR-006 .. FR-016).

`run()` is a generator that yields UI-ready event dicts so the Streamlit
front end can render live progress. The controller never lets the LLM touch
the filesystem or shell directly: every action is executed by a tool under
the application's security policy (SEC-002, SEC-005, SEC-007).
"""
from __future__ import annotations

import time
from typing import Iterator, Optional

from agent import prompts
from core.config import Config
from core.models import (
    AgentIteration, FinalReport, Investigation, InvestigationStatus as S,
    Patch, PatchStatus, ToolExecution,
)
from providers.base import LLMProvider, ProviderError
from security.secrets_scan import scan_and_redact
from security.workspace import Workspace
from tools import code_search, dependency_inspector, file_reader, patch_tools, repository_scanner, test_runner


def _user_facing_reason(action: str, action_input: dict) -> str:
    if action == "search":
        query = str(action_input.get("query", "")).strip()
        return f"Searching for {query!r} to locate relevant code." if query else "Searching for relevant code."
    if action == "read_file":
        path = str(action_input.get("path", "")).strip()
        return f"Inspecting {path} to compare the implementation with the hypothesis." if path else "Inspecting relevant source code."
    if action == "generate_patch":
        return "Preparing a focused patch based on the inspected code and current hypothesis."
    if action == "finish_no_fix":
        return "The available evidence is not sufficient to propose a safe patch."
    return "Selecting the next investigation step."


def _redact_tool_output(text: str) -> tuple:
    redacted, findings = scan_and_redact(text)
    if findings:
        redacted += f"\n[Security notice: {len(findings)} secret-like value(s) redacted.]"
    return redacted, len(findings)


class AgentController:
    def __init__(self, workspace: Workspace, provider: LLMProvider, investigation: Investigation,
                 fallback_provider: Optional[LLMProvider] = None):
        self.ws = workspace
        self.provider = provider
        self.fallback = fallback_provider
        self.inv = investigation
        for p in (provider, fallback_provider):
            if p is not None and p.name == "mock":
                p.workspace = workspace

    # ------------------------------------------------------------------ #
    def _ask_llm(self, context: dict):
        messages = prompts.build_messages(context)
        last_error = None
        for prov, is_fallback in ((self.provider, False), (self.fallback, True)):
            if prov is None:
                continue
            try:
                raw = prov.chat(messages, json_mode=True, max_tokens=1800)
                step = prompts.parse_agent_step(raw)
                return step, (f"Primary provider failed; switched to {prov.name}." if is_fallback else None)
            except (ProviderError, ValueError) as e:
                last_error = e
                continue
        raise last_error or ProviderError("No provider available.")

    def _set(self, status: S):
        self.inv.status = status

    # ------------------------------------------------------------------ #
    def run(self) -> Iterator[dict]:
        inv = self.inv
        self._set(S.ANALYZING)
        scan = repository_scanner.scan(self.ws)
        yield {"type": "observe", "file_count": scan["file_count"],
               "test_files": scan["test_files"], "framework": scan["detected_framework"]}

        last_test_output, last_test_status = "", ""
        failed_diffs = []

        for n in range(1, inv.max_iterations + 1):
            it = AgentIteration(iteration_no=n)
            inv.iterations.append(it)
            yield {"type": "iteration_start", "iteration": n, "max": inv.max_iterations}
            self._set(S.INVESTIGATING)

            history = []
            patch_applied = False
            max_steps = Config.MAX_AGENT_STEPS_PER_ITERATION

            for step_no in range(1, max_steps + 1):
                context = {
                    "bug_description": inv.bug_report.description,
                    "stack_trace": inv.bug_report.stack_trace,
                    "file_tree": scan["files"],
                    "history": history,
                    "last_test_output": last_test_output + (
                        "\n\nPREVIOUS FAILED PATCH (already reverted):\n" + failed_diffs[-1] if failed_diffs else ""),
                    "last_test_status": last_test_status,
                    "step_no": step_no, "iteration_no": n, "max_iterations": inv.max_iterations,
                    "force_patch": step_no == max_steps,
                }
                try:
                    step, notice = self._ask_llm(context)
                except (ProviderError, ValueError) as e:
                    self._set(S.UNRECOVERABLE_ERROR)
                    yield {"type": "error", "message": f"AI provider error: {e}"}
                    yield from self._finish("UNRECOVERABLE_ERROR", f"The AI provider failed: {e}")
                    return
                if notice:
                    yield {"type": "notice", "message": notice}

                action = step.get("action")
                inp = step.get("action_input") or {}
                it.hypothesis = step.get("hypothesis") or it.hypothesis
                it.action = action
                it.reason = _user_facing_reason(action, inp)
                it.next_action = step.get("next_action_hint", "")
                yield {"type": "step", "iteration": n, "step": step_no, "action": action,
                    "reason": it.reason, "hypothesis": it.hypothesis,
                    "next": it.next_action, "files_inspected": list(it.files_inspected),
                    "input": inp if action != "generate_patch" else {}}

                if action == "search":
                    query = str(inp.get("query", "")).strip()
                    hits = code_search.search(self.ws, query) if query else []
                    text = "\n".join(f"{h['file']}:{h['line']}: {h['text']}" for h in hits) or "(no matches)"
                    text, secret_findings = _redact_tool_output(text)
                    it.tool_executions.append(ToolExecution(tool_name="code_search", input=query, output=text))
                    history.append({"tool": "code_search", "result_text": f"search '{query}':\n{text}"})
                    yield {"type": "tool", "tool": "Code Search", "input": query,
                           "output": text, "secret_findings": secret_findings}

                elif action == "find_symbol":
                    symbol = str(inp.get("symbol", "")).strip()
                    hits = code_search.find_symbol(self.ws, symbol) if symbol else []
                    text = "\n".join(
                        f"{hit['file']}:{hit['line']} [{hit['kind']}]: {hit['text']}" for hit in hits
                    ) or "(no matches)"
                    text, secret_findings = _redact_tool_output(text)
                    it.tool_executions.append(ToolExecution(
                        tool_name="symbol_search", input=symbol, output=text))
                    history.append({"tool": "symbol_search", "result_text": f"symbol '{symbol}':\n{text}"})
                    yield {"type": "tool", "tool": "Symbol Search", "input": symbol,
                           "output": text, "secret_findings": secret_findings}

                elif action == "inspect_dependencies":
                    result = dependency_inspector.inspect_dependencies(self.ws)
                    text = "\n".join(
                        f"{item['name']} {item['constraint']} ({item['group']})".strip()
                        for item in result["dependencies"]
                    ) or "(no dependencies declared)"
                    if result["note"]:
                        text += "\n" + result["note"]
                    text, secret_findings = _redact_tool_output(text)
                    it.tool_executions.append(ToolExecution(
                        tool_name="dependency_inspector", input=", ".join(result["manifests"]), output=text))
                    history.append({"tool": "dependency_inspector", "result_text": text})
                    yield {"type": "tool", "tool": "Dependency Inspector",
                           "input": ", ".join(result["manifests"]) or "dependency manifests",
                           "output": text, "secret_findings": secret_findings}

                elif action == "read_file":
                    path = str(inp.get("path", "")).strip()
                    res = file_reader.read_file(self.ws, path)
                    if res["ok"]:
                        it.files_inspected.append(path)
                        text = f"FILE {path}:\n{res['content']}"
                    else:
                        text = f"ERROR: {res['error']}"
                    text, secret_findings = _redact_tool_output(text)
                    it.tool_executions.append(ToolExecution(tool_name="file_reader", input=path,
                                                            output=text[:2000], ok=res["ok"]))
                    history.append({"tool": "file_reader", "result_text": text})
                    yield {"type": "tool", "tool": "File Reader", "input": path,
                           "output": text[:1500], "ok": res["ok"], "secret_findings": secret_findings}

                elif action == "generate_patch":
                    self._set(S.PATCH_PROPOSED)
                    diff = patch_tools.extract_diff(str(inp.get("diff", "")))
                    patch = patch_tools.validate_and_apply(self.ws, diff, str(inp.get("summary", "")))
                    it.patch = patch
                    it.tool_executions.append(ToolExecution(
                        tool_name="patch_applier", input=patch.summary[:200],
                        output=patch.status.value, ok=patch.status == PatchStatus.APPLIED))
                    if patch.status == PatchStatus.APPLIED:
                        self._set(S.PATCH_APPLIED)
                        patch_applied = True
                        yield {"type": "patch", "patch": patch, "iteration": n}
                        break
                    history.append({"tool": "patch_applier",
                                    "result_text": f"Your patch was REJECTED as invalid:\n{patch.summary}"})
                    yield {"type": "notice", "message": "Proposed patch failed validation; asking the agent to retry."}

                elif action == "finish_no_fix":
                    reason = inp.get("reason", "The agent could not propose a confident fix.")
                    self._set(S.HUMAN_INTERVENTION)
                    yield {"type": "notice", "message": reason}
                    yield from self._finish("HUMAN_INTERVENTION", reason)
                    return
                else:
                    history.append({"tool": "controller", "result_text": f"Unknown action '{action}' ignored."})

            if not patch_applied:
                yield {"type": "notice", "message": "No valid patch produced this iteration."}
                last_test_output, last_test_status = "No valid patch was produced.", "NO_PATCH"
                continue

            # TEST
            self._set(S.TESTING)
            yield {"type": "testing", "iteration": n}
            result = test_runner.run_tests(self.ws, timeout=inv.timeout_seconds)
            result.output, secret_findings = _redact_tool_output(result.output)
            it.test_result = result
            yield {"type": "test", "iteration": n, "result": result,
                    "secret_findings": secret_findings}

            if result.passed:
                self._set(S.TEST_PASSED)
                yield from self._finish("COMPLETED",
                                        f"Tests passed after {n} iteration(s). Review the patch and approve it to accept.")
                return

            if result.status == "NO_TESTS":
                self._set(S.HUMAN_INTERVENTION)
                summary = "No tests were found. The proposed patch remains applied but is unverified; review it before approval."
                yield {"type": "notice", "message": summary}
                yield from self._finish("HUMAN_INTERVENTION", summary)
                return

            self._set(S.TEST_FAILED)
            self._set(S.ANALYZING_FAILURE)
            last_test_output, last_test_status = result.output, result.status
            failed_diffs.append(it.patch.diff)
            patch_tools.rollback_patch(self.ws, it.patch)
            yield {"type": "notice", "message": f"Tests failed ({result.status}); patch reverted, re-investigating."}

        self._set(S.MAX_ITERATIONS)
        yield from self._finish("MAX_ITERATIONS",
                                f"Reached the maximum of {inv.max_iterations} iterations without passing tests. "
                                "Human intervention is recommended.")

    # ------------------------------------------------------------------ #
    def _finish(self, outcome: str, summary: str):
        inv = self.inv
        last_patch = next((i.patch for i in reversed(inv.iterations)
                           if i.patch and i.patch.status == PatchStatus.APPLIED), None)
        if outcome == "COMPLETED":
            self._set(S.COMPLETED)
        inv.final_report = FinalReport(outcome=outcome, iterations_used=len(inv.iterations),
                                       accepted_patch=None, summary=summary)
        yield {"type": "done", "outcome": outcome, "summary": summary, "pending_patch": last_patch}
