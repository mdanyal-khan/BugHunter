"""End-to-end self-test of the agent pipeline using the offline Mock provider (no network)."""
import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["BUGHUNTER_WORKSPACE_ROOT"] = "/tmp/bh_selftest"
from core.models import Investigation, BugReport, PatchStatus
from providers import get_provider
from security.workspace import Workspace
from agent.controller import AgentController
from tools import patch_tools
from security.command_policy import run_allowlisted, CommandRejected
from security.workspace import WorkspaceSecurityError

HERE = os.path.dirname(os.path.abspath(__file__))
ok = True
for demo in ("bug1_none_handling", "bug2_calc_error", "bug3_api_error"):
    ws = Workspace()
    ws.load_local_dir(os.path.join(HERE, "demo_repos", demo))
    inv = Investigation(bug_report=BugReport(description="demo bug"), max_iterations=3, provider_name="mock")
    ctrl = AgentController(ws, get_provider("mock"), inv)
    events = list(ctrl.run())
    done = events[-1]
    types = [e["type"] for e in events]
    passed = done["outcome"] == "COMPLETED"
    print(f"{demo}: {done['outcome']}  events={types}")
    ok &= passed
    # rollback test
    patch = done["pending_patch"]
    if patch:
        assert patch_tools.rollback_patch(ws, patch), "rollback failed"
        print("   rollback ->", patch.status.value)
    ws.destroy()

# security checks
ws = Workspace()
try:
    ws.resolve("../../etc/passwd"); print("FAIL traversal"); ok = False
except WorkspaceSecurityError: print("traversal blocked: OK")
try:
    run_allowlisted(["rm", "-rf", "/"], ws.root, 5); print("FAIL allowlist"); ok = False
except CommandRejected: print("rm blocked: OK")
ws.destroy()
print("ALL OK" if ok else "FAILURES")
sys.exit(0 if ok else 1)
