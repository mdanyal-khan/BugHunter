"""
Command Policy (SEC-002) and Timeout Manager (SEC-003).

Only a small allowlist of interpreters/tools may ever be executed inside a
workspace. This check is purely application-level and does not depend on
the LLM "agreeing" to behave — it is the primary defense described in
Section 28.2 (Prompt Injection Protection) of the SRS.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass

ALLOWED_EXECUTABLES = {
    "python", "python3", sys.executable.split(os.sep)[-1],
    "pytest", "git", "dart", "flutter", "node", "npm", "go", "cargo",
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
    for key in ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TEMP", "TMP",
                "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PATHEXT"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _windows_batch_command(cmd: list, env: dict) -> str:
    """Build a cmd.exe invocation for a fixed, non-shell-parameterized SDK action."""
    allowed_subcommands = {"dart": "test", "flutter": "test", "npm": "test"}
    subcommand = allowed_subcommands.get(cmd[0])
    if subcommand is None or cmd[1:] != [subcommand]:
        raise CommandRejected("Only the fixed test subcommand is allowed for Windows batch launchers.")
    launcher = shutil.which(cmd[0])
    if not launcher:
        raise FileNotFoundError(cmd[0])
    comspec = env.get("COMSPEC") or os.path.join(env.get("SYSTEMROOT", r"C:\Windows"), "System32", "cmd.exe")
    command = f'"{launcher}" {subcommand}'
    return f'{subprocess.list2cmdline([comspec])} /d /c "{command}"'


def _resource_limit_preexec(timeout: int):
    if os.name != "posix":
        return None

    def apply_limits():
        import resource

        if hasattr(resource, "RLIMIT_CPU"):
            _, hard_limit = resource.getrlimit(resource.RLIMIT_CPU)
            cpu_limit = max(1, int(timeout))
            if hard_limit != resource.RLIM_INFINITY:
                cpu_limit = min(cpu_limit, hard_limit)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, hard_limit))
        if hasattr(resource, "RLIMIT_AS"):
            _, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
            memory_limit = 2 * 1024 * 1024 * 1024
            if hard_limit != resource.RLIM_INFINITY:
                memory_limit = min(memory_limit, hard_limit)
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, hard_limit))

    return apply_limits


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
    env = _restricted_env()
    run_cmd = cmd
    if os.name == "nt" and os.path.basename(cmd[0]) in {"dart", "flutter", "npm"}:
        run_cmd = _windows_batch_command(cmd, env)
    try:
        proc = subprocess.run(
            run_cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, env=env,
            preexec_fn=_resource_limit_preexec(timeout),
        )
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr, duration_ms)
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(False, -1, e.stdout or "", (e.stderr or "") + "\n[TIMEOUT]", duration_ms, timed_out=True)
    except FileNotFoundError as e:
        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(False, -1, "", str(e), duration_ms)
