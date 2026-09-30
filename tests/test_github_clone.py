import base64
from types import SimpleNamespace

from core.config import Config
from security import workspace as workspace_module
from security.workspace import Workspace


def test_clone_passes_private_token_outside_command_line(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr(Workspace, "_git_init", lambda self: None)
    monkeypatch.setattr(Workspace, "_stats", lambda self: (1, 12))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(workspace_module.subprocess, "run", fake_run)
    workspace = Workspace()
    try:
        result = workspace.clone_github("https://github.com/acme/private-repo", "secret-token", "octocat")

        assert result.ok
        assert captured["command"] == [
            "git", "clone", "--depth", "1", "--", "https://github.com/acme/private-repo.git", "."
        ]
        assert "secret-token" not in " ".join(captured["command"])
        header = captured["env"]["GIT_CONFIG_VALUE_0"]
        assert header == "Authorization: Basic " + base64.b64encode(
            b"octocat:secret-token"
        ).decode("ascii")
        assert "secret-token" not in header
    finally:
        workspace.destroy()


def test_clone_rejects_non_repository_or_non_github_urls(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "WORKSPACE_ROOT", str(tmp_path))

    def unexpected_run(*args, **kwargs):
        raise AssertionError("git must not run for an invalid URL")

    monkeypatch.setattr(workspace_module.subprocess, "run", unexpected_run)
    workspace = Workspace()
    try:
        for url in (
            "http://github.com/acme/repo",
            "https://example.com/acme/repo",
            "https://user:pass@github.com/acme/repo",
            "https://github.com/acme/repo/tree/main",
            "https://github.com/acme/repo?tab=readme",
        ):
            assert not workspace.clone_github(url, "secret-token").ok
    finally:
        workspace.destroy()