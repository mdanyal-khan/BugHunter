"""BugHunter Agent — Streamlit UI entry point.  Run with:  streamlit run app.py"""
from __future__ import annotations

import io
import json
import os
import time
import zipfile

import streamlit as st

from agent.controller import AgentController
from core.config import Config
from core.demos import DEMOS, DEMO_ROOT
from core.models import BugReport, FinalReport, Investigation, PatchStatus
from providers import PROVIDER_LABELS, get_provider
from security.workspace import Workspace
from tools import patch_tools, repository_scanner
from ui import components as C
from ui.styles import CSS

st.set_page_config(page_title="BugHunter Agent", page_icon="🐞", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- state
def init_state():
    defaults = {"ws": None, "inv": None, "events": [], "repo_label": None, "scan": None,
                "bug_desc": "", "stack_trace": "", "notice": None}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def reset_investigation():
    st.session_state.inv = None
    st.session_state.events = []


def _new_workspace():
    if st.session_state.ws is not None:
        st.session_state.ws.destroy()
    ws = Workspace()
    st.session_state.ws = ws
    reset_investigation()
    return ws


def load_demo(key: str):
    demo = DEMOS[key]
    ws = _new_workspace()
    res = ws.load_local_dir(os.path.join(DEMO_ROOT, demo["dir"]))
    st.session_state.repo_label = demo["label"]
    st.session_state.scan = repository_scanner.scan(ws)
    st.session_state.bug_desc = demo["description"]
    st.session_state.stack_trace = demo["stack_trace"]
    st.session_state.notice = ("ok", f"Loaded {demo['label']} ({res.file_count} files).")


def load_zip(uploaded):
    ws = _new_workspace()
    res = ws.extract_zip(uploaded.getvalue())
    if not res.ok:
        ws.destroy()
        st.session_state.ws = None
        st.session_state.notice = ("bad", res.message)
        return
    st.session_state.repo_label = uploaded.name
    st.session_state.scan = repository_scanner.scan(ws)
    st.session_state.notice = ("ok", f"Extracted {uploaded.name} ({res.file_count} files).")


def zip_workspace(ws: Workspace) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in ws.file_tree(max_entries=5000):
            z.write(ws.resolve(rel), rel)
    return buf.getvalue()


def save_report(inv: Investigation):
    try:
        os.makedirs(Config.REPORTS_DIR, exist_ok=True)
        path = os.path.join(Config.REPORTS_DIR, f"report_{inv.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(inv.to_dict(), f, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------- patch actions
def pending_patch(inv):
    for it in reversed(inv.iterations):
        if it.patch and it.patch.status == PatchStatus.APPLIED:
            return it.patch
    return None


def approve(patch):
    inv, ws = st.session_state.inv, st.session_state.ws
    patch.status = PatchStatus.APPROVED
    last = inv.iterations[-1].test_result if inv.iterations else None
    verified = bool(last and last.passed)
    note = "" if verified else " ⚠️ This fix is UNVERIFIED — tests did not pass."
    inv.final_report = FinalReport(
        outcome=inv.final_report.outcome if inv.final_report else "COMPLETED",
        iterations_used=len(inv.iterations), accepted_patch=patch,
        summary=f"Patch approved by the developer.{note}")
    save_report(inv)


def reject(patch):
    inv, ws = st.session_state.inv, st.session_state.ws
    patch_tools.rollback_patch(ws, patch)
    patch.status = PatchStatus.REJECTED
    if inv.final_report:
        inv.final_report.accepted_patch = None
        inv.final_report.summary = "Patch rejected by the developer and reverted."


def revert(patch):
    patch_tools.rollback_patch(st.session_state.ws, patch)
    inv = st.session_state.inv
    if inv.final_report:
        inv.final_report.accepted_patch = None
        inv.final_report.summary = "Patch reverted by the developer."


# ---------------------------------------------------------------- sidebar
def sidebar():
    sb = st.sidebar
    sb.markdown("### ⚙️ Configuration")
    provider = sb.selectbox("AI provider", list(PROVIDER_LABELS), format_func=PROVIDER_LABELS.get,
                            index=list(PROVIDER_LABELS).index(
                                Config.DEFAULT_PROVIDER if Config.DEFAULT_PROVIDER in PROVIDER_LABELS else "groq"))
    default_model = {"groq": Config.GROQ_MODEL, "huggingface": Config.HF_MODEL, "mock": "mock-scripted-v1"}[provider]
    model = sb.text_input("Model", value=default_model, disabled=(provider == "mock"), key=f"model_{provider}")
    api_key = ""
    if provider != "mock":
        env_key = Config.GROQ_API_KEY if provider == "groq" else Config.HF_API_KEY
        api_key = sb.text_input("API key", type="password", key=f"key_{provider}",
                                placeholder="Using environment variable" if env_key else "Paste your key")
        api_key = api_key or env_key
        if api_key:
            sb.success("API key configured", icon="🔑")
        else:
            sb.warning("No API key yet. Set it here or in .env — or pick Offline Demo.", icon="🔑")
    else:
        sb.info("Offline demo mode runs the full loop on the bundled demo repos — no key or internet needed.", icon="🛰️")

    sb.markdown("### 🎛️ Investigation limits")
    max_iter = sb.slider("Maximum iterations", 1, 10, Config.MAX_ITERATIONS_DEFAULT)
    timeout = sb.slider("Test timeout (seconds)", 10, 300, Config.TIMEOUT_SECONDS_DEFAULT, step=10)
    fallback = sb.toggle("Fall back to the other provider on failure", value=True)

    sb.markdown("---")
    if sb.button("🗑️ Reset session", use_container_width=True):
        if st.session_state.ws:
            st.session_state.ws.destroy()
        for k in ("ws", "inv", "events", "repo_label", "scan", "bug_desc", "stack_trace", "notice"):
            st.session_state.pop(k, None)
        st.rerun()
    sb.caption("Repository code runs only inside an isolated per-session workspace. "
               "Nothing is applied as final without your approval.")
    return dict(provider=provider, model=model, api_key=api_key, max_iter=max_iter,
                timeout=timeout, fallback=fallback)


def build_providers(cfg):
    primary = get_provider(cfg["provider"], api_key=cfg["api_key"] or None, model=cfg["model"])
    fb = None
    if cfg["fallback"] and cfg["provider"] in ("groq", "huggingface"):
        other = "huggingface" if cfg["provider"] == "groq" else "groq"
        other_key = st.session_state.get(f"key_{other}") or (Config.HF_API_KEY if other == "huggingface" else Config.GROQ_API_KEY)
        if other_key:
            fb = get_provider(other, api_key=other_key)
    return primary, fb


# ---------------------------------------------------------------- sections
def repository_section():
    C.step_title(1, "Load a repository")
    tab_zip, tab_demo = st.tabs(["📦 Upload ZIP", "🎯 Demo repositories"])
    with tab_zip:
        up = st.file_uploader("Python repository (.zip)", type=["zip"], label_visibility="collapsed")
        if up is not None and st.session_state.repo_label != up.name:
            load_zip(up)
            st.rerun()
    with tab_demo:
        cols = st.columns(3)
        for col, (key, d) in zip(cols, DEMOS.items()):
            with col:
                st.markdown(f'<div class="card"><div class="head">{d["label"]}</div>'
                            f'<div class="val" style="color:#8f9bc4">{d["blurb"]}</div></div>',
                            unsafe_allow_html=True)
                st.button("Load", key=f"load_{key}", on_click=load_demo, args=(key,), use_container_width=True)

    note = st.session_state.notice
    if note:
        (st.success if note[0] == "ok" else st.error)(note[1])
        st.session_state.notice = None

    scan = st.session_state.scan
    if scan:
        C.metrics([("Repository", f'<span style="font-size:1rem">{st.session_state.repo_label}</span>'),
                   ("Files", scan["file_count"]), ("Python files", scan["python_file_count"]),
                   ("Test files", len(scan["test_files"]))])
        with st.expander("Repository structure"):
            st.code("\n".join(scan["files"]), language="text")


def bug_section(cfg):
    C.step_title(2, "Describe the bug")
    st.text_area("Bug description", key="bug_desc", height=110,
                 placeholder="What is going wrong? What did you expect instead?")
    st.text_area("Stack trace / error log (optional)", key="stack_trace", height=110)

    ready = st.session_state.ws is not None and st.session_state.bug_desc.strip()
    if st.button("🚀 Start investigation", type="primary", disabled=not ready):
        if cfg["provider"] != "mock" and not cfg["api_key"]:
            st.error("This provider needs an API key. Add one in the sidebar, or choose Offline Demo.")
        else:
            run_investigation(cfg)
    if not ready:
        st.caption("Load a repository and describe the bug to enable the agent.")


def run_investigation(cfg):
    ws = st.session_state.ws
    ws.rollback_to(ws.baseline)  # always start from the originally uploaded state
    inv = Investigation(
        bug_report=BugReport(description=st.session_state.bug_desc.strip(),
                             stack_trace=st.session_state.stack_trace.strip()),
        provider_name=cfg["provider"], model_name=cfg["model"],
        max_iterations=cfg["max_iter"], timeout_seconds=cfg["timeout"], workspace_path=ws.root)
    st.session_state.inv = inv
    st.session_state.events = []
    primary, fb = build_providers(cfg)
    ctrl = AgentController(ws, primary, inv, fallback_provider=fb)

    st.markdown("#### 🔴 Live investigation")
    tracker = st.empty()
    feed = st.container()
    for ev in ctrl.run():
        st.session_state.events.append(ev)
        tracker.markdown(C.tracker_html(C.phase_for_event(ev)), unsafe_allow_html=True)
        with feed:
            C.render_event(ev)
    save_report(inv)
    st.rerun()


def results_section():
    inv = st.session_state.inv
    if inv is None:
        return
    events = st.session_state.events
    st.markdown("---")
    C.step_title(3, "Results")

    tests = [i.test_result for i in inv.iterations if i.test_result]
    last = tests[-1] if tests else None
    pill = "ok" if (last and last.passed) else "bad"
    C.metrics([
        ("Status", C.status_pill(inv.status.value.replace("_", " "), pill if last else "warn")),
        ("Iterations", f"{len(inv.iterations)} / {inv.max_iterations}"),
        ("Tests passed", last.passed_count if last else "—"),
        ("Tests failed", last.failed_count if last else "—"),
    ])

    t_act, t_patch, t_test, t_report = st.tabs(
        ["🔍 Agent activity", "🩹 Patch viewer", "✅ Test results", "📋 Final report"])

    with t_act:
        for ev in events:
            C.render_event(ev)

    with t_patch:
        patches = [(i.iteration_no, i.patch) for i in inv.iterations if i.patch]
        if not patches:
            st.info("The agent has not produced a patch yet.")
        for n, p in patches:
            kind = {"applied": "info", "approved": "ok", "rejected": "bad", "reverted": "warn",
                    "invalid": "bad"}.get(p.status.value, "info")
            st.markdown(f'**Iteration {n}** {C.status_pill(p.status.value.upper(), kind)}', unsafe_allow_html=True)
            st.caption(f"Summary: {p.summary or '—'}  ·  Files: {', '.join(p.files_changed) or '—'}")
            C.render_diff(p.diff)
        pp = pending_patch(inv)
        if pp:
            st.markdown("##### Your decision")
            if last and not last.passed:
                st.warning("Tests have not passed — approving would mark this fix as unverified.")
            c1, c2, c3 = st.columns(3)
            c1.button("✅ Approve", use_container_width=True, type="primary", on_click=approve, args=(pp,))
            c2.button("❌ Reject", use_container_width=True, on_click=reject, args=(pp,))
            c3.button("↩️ Revert", use_container_width=True, on_click=revert, args=(pp,))
        approved = next((p for _, p in patches if p.status == PatchStatus.APPROVED), None)
        if approved:
            st.success("Patch approved. Download the patched project below.")
            st.download_button("⬇️ Download patched project (.zip)", zip_workspace(st.session_state.ws),
                               file_name="bughunter_patched_project.zip", mime="application/zip")
            st.download_button("⬇️ Download patch (.diff)", approved.diff, file_name="bughunter_fix.diff")

    with t_test:
        if not tests:
            st.info("No tests have been run yet.")
        for i in inv.iterations:
            if i.test_result:
                C.render_test_result(i.test_result, i.iteration_no)

    with t_report:
        fr = inv.final_report
        if not fr:
            st.info("The report appears when the investigation finishes.")
        else:
            md = fr.to_markdown(inv)
            st.markdown(md)
            d1, d2 = st.columns(2)
            d1.download_button("⬇️ Report (.md)", md, file_name=f"bughunter_report_{inv.id}.md", use_container_width=True)
            d2.download_button("⬇️ Report (.json)", json.dumps(inv.to_dict(), indent=2),
                               file_name=f"bughunter_report_{inv.id}.json", use_container_width=True)


# ---------------------------------------------------------------- main
def main():
    init_state()
    cfg = sidebar()
    C.hero()
    if st.session_state.inv is None:
        st.markdown(C.tracker_html(-1), unsafe_allow_html=True)
    repository_section()
    bug_section(cfg)
    results_section()


main()
