"""
Workspace Isolation (SEC-001, SEC-005) and checkpoint/rollback (SEC-012, FR-019).

Every investigation session gets its own directory under Config.WORKSPACE_ROOT.
The workspace is a git repository purely as an implementation convenience for
producing/validating unified diffs and cheap checkpointing — it is not related
to the user's own version control history, and the original upload is never
modified (FR-011).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import Config


class WorkspaceSecurityError(Exception):
    """Raised when an operation would escape the isolated workspace."""


@dataclass
class ExtractionResult:
    ok: bool
    message: str
    file_count: int = 0
    total_size: int = 0


class Workspace:
    """An isolated, per-session directory containing the extracted repository."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or uuid.uuid4().hex[:10]
        self.root = os.path.join(Config.WORKSPACE_ROOT, f"session_{self.session_id}")
        os.makedirs(self.root, exist_ok=True)
        self._git_ready = False
        self.baseline = None

    # ------------------------------------------------------------------ #
    # Path safety (SEC-005: path traversal protection)
    # ------------------------------------------------------------------ #
    def resolve(self, relative_path: str) -> str:
        """Resolve a workspace-relative path and guarantee it stays inside root."""
        candidate = os.path.realpath(os.path.join(self.root, relative_path))
        root_real = os.path.realpath(self.root)
        if candidate != root_real and not candidate.startswith(root_real + os.sep):
            raise WorkspaceSecurityError(
                f"Path '{relative_path}' resolves outside the isolated workspace and was blocked."
            )
        return candidate

    # ------------------------------------------------------------------ #
    # Extraction (FR-001, FR-002)
    # ------------------------------------------------------------------ #
    def extract_zip(self, zip_bytes: bytes) -> ExtractionResult:
        max_bytes = Config.MAX_UPLOAD_MB * 1024 * 1024
        if len(zip_bytes) > max_bytes:
            return ExtractionResult(False, f"Archive exceeds the {Config.MAX_UPLOAD_MB} MB limit.")

        tmp_zip = os.path.join(self.root, "_upload.zip")
        with open(tmp_zip, "wb") as f:
            f.write(zip_bytes)

        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                total_size = 0
                safe_members = []
                for member in zf.infolist():
                    # Reject zip-slip / path traversal entries outright.
                    member_path = os.path.realpath(os.path.join(self.root, member.filename))
                    if not member_path.startswith(os.path.realpath(self.root) + os.sep):
                        continue
                    total_size += member.file_size
                    safe_members.append(member)
                if total_size > max_bytes * 4:  # guard against zip bombs
                    return ExtractionResult(False, "Archive expands well beyond the allowed size limit.")
                zf.extractall(self.root, members=safe_members)
        except zipfile.BadZipFile:
            return ExtractionResult(False, "The uploaded file is not a valid ZIP archive.")
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)

        self._flatten_single_root_dir()
        file_count, total_size = self._stats()
        self._git_init()
        return ExtractionResult(True, "Repository extracted successfully.", file_count, total_size)

    def load_local_dir(self, source_dir: str) -> ExtractionResult:
        """Used for bundled demo repositories (Section 30)."""
        for item in os.listdir(source_dir):
            s = os.path.join(source_dir, item)
            d = os.path.join(self.root, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        file_count, total_size = self._stats()
        self._git_init()
        return ExtractionResult(True, "Demo repository loaded.", file_count, total_size)

    def _flatten_single_root_dir(self) -> None:
        entries = [e for e in os.listdir(self.root) if not e.startswith(".")]
        if len(entries) == 1 and os.path.isdir(os.path.join(self.root, entries[0])):
            inner = os.path.join(self.root, entries[0])
            for item in os.listdir(inner):
                shutil.move(os.path.join(inner, item), os.path.join(self.root, item))
            os.rmdir(inner)

    def _stats(self):
        file_count, total_size = 0, 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for fn in filenames:
                file_count += 1
                try:
                    total_size += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass
        return file_count, total_size

    # ------------------------------------------------------------------ #
    # Checkpointing via a local git repo (SEC-011, SEC-012, FR-019)
    # ------------------------------------------------------------------ #
    def _run_git(self, *args, check=True):
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True,
            timeout=15, check=check,
        )

    def _git_init(self) -> None:
        if self._git_ready:
            return
        try:
            self._run_git("init", "-q")
            self._run_git("config", "user.email", "agent@bughunter.local")
            self._run_git("config", "user.name", "BugHunter Agent")
            self._run_git("add", "-A")
            self._run_git("commit", "-q", "-m", "baseline: uploaded repository", check=False)
            self._git_ready = True
            self.baseline = self.current_commit()
        except (subprocess.SubprocessError, FileNotFoundError):
            self._git_ready = False

    def checkpoint(self, message: str) -> Optional[str]:
        """Commit the current state and return the commit SHA (or None if unavailable)."""
        if not self._git_ready:
            return None
        try:
            self._run_git("add", "-A")
            self._run_git("commit", "-q", "-m", message, check=False)
            result = self._run_git("rev-parse", "HEAD")
            return result.stdout.strip()
        except subprocess.SubprocessError:
            return None

    def rollback_to(self, commit_sha: Optional[str]) -> bool:
        """Hard-reset the workspace to a previous checkpoint (SEC-012)."""
        if not self._git_ready or not commit_sha:
            return False
        try:
            self._run_git("reset", "--hard", commit_sha)
            self._run_git("clean", "-fd")
            return True
        except subprocess.SubprocessError:
            return False

    def current_commit(self) -> Optional[str]:
        if not self._git_ready:
            return None
        try:
            return self._run_git("rev-parse", "HEAD").stdout.strip()
        except subprocess.SubprocessError:
            return None

    # ------------------------------------------------------------------ #
    # Teardown (DATA-003: repository content not retained beyond session)
    # ------------------------------------------------------------------ #
    def destroy(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def file_tree(self, max_entries: int = 400):
        tree = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "venv", ".venv")]
            rel_dir = os.path.relpath(dirpath, self.root)
            for fn in sorted(filenames):
                rel = fn if rel_dir == "." else os.path.join(rel_dir, fn)
                tree.append(rel)
                if len(tree) >= max_entries:
                    return tree
        return tree
