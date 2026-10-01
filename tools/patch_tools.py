"""TOOL-008 Patch Generator, TOOL-009 Patch Applier, TOOL-010 Diff Viewer,
TOOL-011 Rollback.

Patch Generator's actual LLM call lives in the agent layer (agent/controller.py)
since it needs conversation context; this module handles everything that
happens to a diff once the LLM has produced it: validation, application,
rendering, and rollback.
"""
from __future__ import annotations

import os
import re
import subprocess

from core.models import Patch, PatchStatus
from security.workspace import Workspace

_DIFF_FENCE_RE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)
_FILE_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$", re.MULTILINE)
_BARE_HUNK_RE = re.compile(r"^@@\s*$")


def extract_diff(raw_text: str) -> str:
    """Pulls a unified diff out of an LLM response, tolerating markdown fences."""
    m = _DIFF_FENCE_RE.search(raw_text)
    text = m.group(1) if m else raw_text
    text = text.strip()
    if not text.endswith("\n"):
        text += "\n"
    return text


def files_touched(diff_text: str) -> list:
    return sorted(set(_FILE_HEADER_RE.findall(diff_text)))


def _repair_bare_hunk_headers(workspace: Workspace, diff_text: str) -> str:
    """Fill bare @@ headers only when their old-side context is a unique match."""
    lines = diff_text.splitlines(keepends=True)
    repaired = []
    index = 0
    current_path = None
    previous_delta = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith("+++ "):
            current_path = line[4:].strip()
            if current_path.startswith("b/"):
                current_path = current_path[2:]
            previous_delta = 0
            repaired.append(line)
            index += 1
            continue

        if not _BARE_HUNK_RE.match(line.rstrip("\r\n")) or not current_path:
            repaired.append(line)
            index += 1
            continue

        end = index + 1
        while end < len(lines) and not lines[end].startswith(("@@", "--- ", "+++ ")):
            end += 1
        hunk = lines[index + 1:end]
        old_lines = [item[1:].rstrip("\r\n") for item in hunk
                     if item.startswith((" ", "-"))]
        new_count = sum(item.startswith((" ", "+")) for item in hunk)

        try:
            target = workspace.resolve(current_path)
            with open(target, "r", encoding="utf-8", newline="") as source:
                source_lines = source.read().splitlines()
        except (OSError, UnicodeError):
            source_lines = []

        matches = [start for start in range(len(source_lines) - len(old_lines) + 1)
                   if old_lines and source_lines[start:start + len(old_lines)] == old_lines]
        if len(matches) == 1:
            old_start = matches[0] + 1
            new_start = max(1, old_start + previous_delta)
            old_count = len(old_lines)
            repaired.append(f"@@ -{old_start},{old_count} +{new_start},{new_count} @@\n")
            previous_delta += new_count - old_count
        else:
            repaired.append(line)
        repaired.extend(hunk)
        index = end

    return "".join(repaired)


def validate_and_apply(workspace: Workspace, diff_text: str, summary: str = "") -> Patch:
    """Validates a unified diff with `git apply --check`, then applies it (SEC-011)."""
    diff_text = _repair_bare_hunk_headers(workspace, diff_text)
    patch = Patch(diff=diff_text, summary=summary, files_changed=files_touched(diff_text))

    if not diff_text.strip():
        patch.status = PatchStatus.INVALID
        return patch

    checkpoint = workspace.checkpoint("pre-patch checkpoint")
    patch.checkpoint_ref = checkpoint

    patch_file = os.path.join(workspace.root, "_agent_patch.diff")
    with open(patch_file, "w", encoding="utf-8", newline="") as f:
        f.write(diff_text)

    try:
        check = subprocess.run(
            ["git", "apply", "--check", "--recount", "--whitespace=fix", patch_file],
            cwd=workspace.root, capture_output=True, text=True, timeout=15,
        )
        if check.returncode != 0:
            patch.status = PatchStatus.INVALID
            patch.summary = (patch.summary + f"\n\n[Validation failed]\n{check.stderr}").strip()
            return patch

        apply_result = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=fix", patch_file],
            cwd=workspace.root, capture_output=True, text=True, timeout=15,
        )
        if apply_result.returncode != 0:
            patch.status = PatchStatus.INVALID
            patch.summary = (patch.summary + f"\n\n[Apply failed]\n{apply_result.stderr}").strip()
            return patch

        patch.status = PatchStatus.APPLIED
        workspace.checkpoint(f"applied patch: {summary[:60]}")
        return patch
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        patch.status = PatchStatus.INVALID
        patch.summary = (patch.summary + f"\n\n[Error applying patch] {e}").strip()
        return patch
    finally:
        if os.path.exists(patch_file):
            os.remove(patch_file)


def rollback_patch(workspace: Workspace, patch: Patch) -> bool:
    """TOOL-011 Rollback — restores the workspace to the patch's pre-apply checkpoint."""
    ok = workspace.rollback_to(patch.checkpoint_ref)
    if ok:
        patch.status = PatchStatus.REVERTED
    return ok


def render_diff_html(diff_text: str) -> str:
    """Renders a unified diff as syntax-highlighted HTML for the Streamlit UI."""
    rows = []
    for line in diff_text.splitlines():
        escaped = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        if line.startswith("+++") or line.startswith("---"):
            cls = "diff-file"
        elif line.startswith("@@"):
            cls = "diff-hunk"
        elif line.startswith("+"):
            cls = "diff-add"
        elif line.startswith("-"):
            cls = "diff-del"
        else:
            cls = "diff-ctx"
        rows.append(f'<div class="{cls}">{escaped or "&nbsp;"}</div>')
    return '<div class="diff-viewer">' + "".join(rows) + "</div>"
