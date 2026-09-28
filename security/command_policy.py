"""
Command Policy (SEC-002) and Timeout Manager (SEC-003).

Only a small allowlist of interpreters/tools may ever be executed inside a
workspace. This check is purely application-level and does not depend on
the LLM "agreeing" to behave — it is the primary defense described in
Section 28.2 (Prompt Injection Protection) of the SRS.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass

ALLOWED_EXECUTABLES = {
    "python", "python3", sys.executable.split(os.sep)[-1],
    "pytest", "git",
}


class CommandRejected(Exception):
    pass


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


def _restricted_env() -> dict:
    """Environment for workspace subprocesses: no host secrets (SEC-010)."""
    env = {}
    for key in ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TEMP", "TMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_allowlisted(cmd: list, cwd: str, timeout: int) -> CommandResult:
    """Execute a command inside the workspace if (and only if) it is allowlisted."""
    if not cmd:
        raise CommandRejected("Empty command.")
    exe = os.path.basename(cmd[0])
    if exe not in ALLOWED_EXECUTABLES:
        raise CommandRejected(
            f"Command '{exe}' is not on the allowlist ({sorted(ALLOWED_EXECUTABLES)}) and was blocked."
        )
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, env=_restricted_env(),
        )
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr, duration_ms)
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(False, -1, e.stdout or "", (e.stderr or "") + "\n[TIMEOUT]", duration_ms, timed_out=True)
    except FileNotFoundError as e:
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(False, -1, "", str(e), duration_ms)
