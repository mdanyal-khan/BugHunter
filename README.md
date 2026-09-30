# 🐞 BugHunter Agent

Agentic AI debugging assistant (48-hour hackathon MVP). Upload a Python repo (ZIP) or clone a GitHub repository, describe a bug, and the
agent runs an **Observe → Reason → Act → Test → Observe Again** loop: it searches and reads code, forms a
hypothesis, proposes a patch, applies it in an **isolated workspace**, runs the tests, and iterates on
failure. You review the diff and **approve / reject / revert**.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add GROQ_API_KEY (primary) and/or HF_API_KEY
streamlit run app.py
```
No key yet? Choose **Offline Demo** in the sidebar and load one of the 3 bundled demo repositories — the
full loop runs with no internet (Demo 2 deliberately fails once, then recovers, to show the feedback loop).

## Load a GitHub repository
Choose **GitHub URL**, enter a repository URL such as `https://github.com/owner/repo`, and select **Clone repository**.
Public repositories do not need credentials. For private repositories, provide a GitHub personal access token
with read access to repository contents and the associated GitHub username. GitHub App tokens can use
`x-access-token` as the username. Credentials are used only for the clone and are not saved to disk.

## Architecture (see SRS §22)
| Layer | Code |
|---|---|
| Presentation | `app.py`, `ui/` |
| Agent | `agent/controller.py` (loop), `agent/prompts.py` (Prompt Manager + JSON step contract) |
| AI Provider | `providers/` — `LLMProvider` interface, `GroqProvider`, `HuggingFaceProvider`, `MockProvider` (offline demo) |
| Tools | `tools/` — scanner, code/symbol search, file reader, test discovery/runner, patch apply/diff/rollback |
| Security | `security/` — workspace isolation + path-traversal guard, command allowlist + timeouts, secret redaction, untrusted-data wrapping |

## Security notes (honest scope)
Repository content is treated as untrusted. The LLM only *proposes* actions; the app executes them under an
allowlist (`python`, `pytest`, `git`), timeouts, a scrubbed environment, and workspace path checks. This is
**not** container-grade sandboxing — run untrusted repos in a VM/container for anything beyond a demo.
POSIX hosts additionally apply CPU and address-space limits to workspace commands; Windows enforces command
timeouts and the allowlist but does not currently apply equivalent process memory quotas.

## Verify
`python selftest.py` runs the whole pipeline offline on all three demo bugs plus security checks.
Demo 3's README contains an intentional prompt-injection trap (SRS TC-010).

## Config
Env vars: `GROQ_API_KEY`, `GROQ_MODEL`, `HF_API_KEY`, `HF_MODEL`, `DEFAULT_PROVIDER`
(also `BUGHUNTER_MAX_ITERATIONS`, `BUGHUNTER_TIMEOUT_SECONDS`, `BUGHUNTER_WORKSPACE_ROOT`).
Flutter/Dart support is a documented future extension, not part of the MVP.
