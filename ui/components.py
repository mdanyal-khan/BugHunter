"""Reusable Streamlit UI components (Section 25 of the SRS)."""
from __future__ import annotations

from html import escape

import streamlit as st

from tools.patch_tools import render_diff_html

PHASES = ["Observe", "Reason", "Act", "Test", "Observe Again"]
PHASE_ICONS = ["👁️", "🧠", "🛠️", "🧪", "🔁"]

ACTION_LABELS = {
    "search": "Searching the codebase",
    "find_symbol": "Finding symbol definitions and references",
    "inspect_dependencies": "Inspecting declared dependencies",
    "read_file": "Reading a source file",
    "generate_patch": "Generating a patch",
    "finish_no_fix": "Stopping — no confident fix",
}


def tracker_html(active: int) -> str:
    """active: index into PHASES currently running (-1 = idle)."""
    cells = []
    for i, (p, ic) in enumerate(zip(PHASES, PHASE_ICONS)):
        cls = "on" if i == active else ("done" if 0 <= active and i < active else "")
        cells.append(f'<div class="ph {cls}">{ic} {p}</div>')
    return f'<div class="tracker">{"".join(cells)}</div>'


def phase_for_event(ev: dict) -> int:
    t = ev["type"]
    if t == "observe":
        return 0
    if t == "step":
        return 1
    if t in ("tool", "patch"):
        return 2
    if t in ("testing", "test"):
        return 3
    if t in ("notice", "iteration_start"):
        return 4
    return -1


def hero():
    st.markdown(
        """
        <div class="hero">
          <h1>🐞 BugHunter Agent</h1>
          <p>Agentic AI debugging: it inspects your repository, reasons about the bug, patches it in an
          isolated workspace, runs the tests, and keeps iterating until they pass.</p>
          <div class="chips">
            <span class="chip">Observe → Reason → Act → Test → Observe Again</span>
            <span class="chip">Isolated workspace</span>
            <span class="chip">Human approval required</span>
            <span class="chip">Groq · Hugging Face</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def step_title(num: int, text: str):
    st.markdown(f'<div class="step-title"><span class="step-num">{num}</span>{escape(text)}</div>',
                unsafe_allow_html=True)


def metrics(items: list):
    html = "".join(f'<div class="metric"><div class="k">{escape(k)}</div><div class="v">{v}</div></div>'
                   for k, v in items)
    st.markdown(f'<div class="metrics">{html}</div>', unsafe_allow_html=True)


def status_pill(text: str, kind: str = "info") -> str:
    return f'<span class="pill {kind}">{escape(text)}</span>'


def render_diff(diff: str):
    st.markdown(render_diff_html(diff), unsafe_allow_html=True)


def render_test_result(res, iteration: int):
    kind = "ok" if res.passed else "bad"
    st.markdown(
        f'<div class="card"><div class="head">Iteration {iteration} · {status_pill(res.status, kind)}</div>'
        f'<div class="lbl">Command</div><div class="val"><code>{escape(res.command)}</code></div>'
        f'<div class="lbl">Duration · Passed · Failed</div>'
        f'<div class="val">{res.duration_ms} ms · {res.passed_count} passed · {res.failed_count} failed</div></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Test output", expanded=not res.passed):
        st.code(res.output or "(no output)", language="text")


def render_event(ev: dict):
    t = ev["type"]
    if t == "observe":
        st.markdown(
            f'<div class="card"><div class="head">👁️ Observed the repository</div>'
            f'<div class="val">{ev["file_count"]} files · {len(ev["test_files"])} test file(s) · '
            f'framework: {escape(ev["framework"])}</div></div>', unsafe_allow_html=True)
    elif t == "iteration_start":
        st.markdown(f'<div class="iter">Iteration {ev["iteration"]} / {ev["max"]}</div>', unsafe_allow_html=True)
    elif t == "step":
        label = ACTION_LABELS.get(ev["action"], ev["action"])
        target = ""
        if ev.get("input"):
            target = " · " + ", ".join(f"<code>{escape(str(v))}</code>" for v in ev["input"].values())
        inspected = ", ".join(ev.get("files_inspected", [])) or "—"
        st.markdown(
            f'<div class="card step"><div class="lbl" style="margin-top:0">Current action</div>'
            f'<div class="val"><b>{escape(label)}</b>{target}</div>'
            f'<div class="lbl">Reason</div><div class="val">{escape(ev["reason"] or "—")}</div>'
            f'<div class="lbl">Files inspected</div><div class="val">{escape(inspected)}</div>'
            f'<div class="lbl">Current hypothesis</div><div class="val">{escape(ev["hypothesis"] or "—")}</div>'
            f'<div class="lbl">Next action</div><div class="val">{escape(ev["next"] or "—")}</div></div>',
            unsafe_allow_html=True)
    elif t == "tool":
        icon = "✅" if ev.get("ok", True) else "⚠️"
        with st.expander(f'{icon} {ev["tool"]} — {ev["input"]}'):
            if ev.get("secret_findings"):
                st.warning(f"Redacted {ev['secret_findings']} secret-like value(s) from this output.")
            st.code(ev["output"], language="text")
    elif t == "patch":
        p = ev["patch"]
        st.markdown(
            f'<div class="card"><div class="head">🩹 Patch applied to isolated workspace '
            f'{status_pill("APPLIED", "info")}</div><div class="val">{escape(p.summary or "")}</div>'
            f'<div class="lbl">Files changed</div><div class="val">{escape(", ".join(p.files_changed))}</div></div>',
            unsafe_allow_html=True)
    elif t == "testing":
        st.info("🧪 Running tests in the isolated workspace…")
    elif t == "test":
        if ev.get("secret_findings"):
            st.warning(f"Redacted {ev['secret_findings']} secret-like value(s) from test output.")
        render_test_result(ev["result"], ev["iteration"])
    elif t == "notice":
        st.warning(ev["message"], icon="🔁")
    elif t == "error":
        st.error(ev["message"])
    elif t == "done":
        cls = {"COMPLETED": "ok", "MAX_ITERATIONS": "warn", "HUMAN_INTERVENTION": "warn"}.get(ev["outcome"], "bad")
        st.markdown(f'<div class="banner {cls}"><b>{escape(ev["outcome"].replace("_", " ").title())}</b>'
                    f'<div>{escape(ev["summary"])}</div></div>', unsafe_allow_html=True)
