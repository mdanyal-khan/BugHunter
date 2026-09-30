from security import command_policy


def test_workspace_environment_excludes_provider_credentials(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_private_example")
    monkeypatch.setenv("HF_API_KEY", "hf_private_example")

    env = command_policy._restricted_env()

    assert "GROQ_API_KEY" not in env
    assert "HF_API_KEY" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_resource_limits_are_enabled_only_on_posix(monkeypatch):
    monkeypatch.setattr(command_policy.os, "name", "nt")
    assert command_policy._resource_limit_preexec(60) is None