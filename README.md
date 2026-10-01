# 🐞 BugHunter Agent
**Find the defect. Follow the evidence. Review the fix.**

BugHunter is an AI-assisted debugging workbench for real repositories. Describe a bug, then watch the agent inspect code, form a hypothesis, propose a patch, and run the project’s tests inside an isolated workspace. You stay in control: review the diff, then approve, reject, or revert it.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Test runners](https://img.shields.io/badge/Test%20runners-Python%20%7C%20Dart%20%7C%20JS%20%7C%20Go%20%7C%20Rust-087F70)

> **The loop:** Observe → Reason → Act → Test → Observe Again

## What You Can Do

| Capability | How it works |
|---|---|
| Bring a repository | Upload a ZIP or clone a GitHub repository into a per-session workspace. |
| Investigate a bug | Provide a description and optional stack trace; the agent searches, reads, and inspects dependencies. |
| Validate a proposed fix | Run supported project test suites and feed failures back into the next iteration. |
| Stay in control | Inspect the diff and approve, reject, or revert the patch before accepting it. |
| Keep working through provider limits | Automatically fail over between Groq and Hugging Face when both credentials are configured. |
| Try it without an API key | Use Offline Demo with the three bundled bug repositories. |

## Quick Start

**Requirements:** Python 3.10+, Git, and the SDKs/dependencies for the language projects you want to test.

Create and activate a virtual environment, then install the app dependencies.

**Windows PowerShell**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add at least one provider key to `.env`, then start the app:

```bash
streamlit run app.py
```

No API key yet? Skip provider setup, choose **Offline Demo** in the sidebar, and load a bundled repository. Demo 2 intentionally fails on its first test run, then demonstrates the repair loop.

## Investigation Flow

1. **Load** a ZIP, a GitHub repository, or an offline demo.
2. **Describe** the bug and paste an optional stack trace.
3. **Watch** the agent inspect the repository and work through its debugging loop.
4. **Review** the patch and test results.
5. **Approve, reject, or revert** the change; download the patched project or report when appropriate.

For a public GitHub repository, provide its HTTPS URL. Private repositories require a personal access token with repository read access and the associated username. GitHub App tokens can use `x-access-token` as the username. Clone credentials are used for that operation and are not written to the repository.

## Languages & Test Runners

The scanner recognizes these source languages and common test-file conventions:

| Ecosystem | Discovery | Test command |
|---|---|---|
| Python | `test_*.py`, `*_test.py` | `pytest`; a bundled self-runner fallback is used if pytest is unavailable. |
| Flutter / Dart | `*_test.dart` | `flutter test` for Flutter projects; otherwise `dart test`. |
| JavaScript / TypeScript | `*.test.*`, `*.spec.*` | `npm test` when a test script exists; otherwise `node --test`. TypeScript projects should configure their own test script/loader. |
| Go | `*_test.go` | `go test -v ./...` |
| Rust | Rust test sources in a Cargo project | `cargo test` |

In mixed-language repositories, detected suites run sequentially. Install each project’s SDK and dependencies before investigating; BugHunter does not install project dependencies or provide language-specific static analysis. If a required test tool is missing, the run reports which tool is unavailable.

## AI Provider Failover

Automatic failover is enabled by default. Add both `GROQ_API_KEY` and `HF_API_KEY` to `.env`, or enter the primary and fallback keys in the sidebar. On a rate limit, BugHunter tries the other provider for that request and checks the configured primary again on the next request. If both providers fail, the live investigation reports both errors and suggests checking the keys/quotas or retrying later.

The default Hugging Face model is `openai/gpt-oss-120b:fastest`. If Hugging Face reports that a selected model is unsupported, BugHunter retries with this configured fallback model. Your Hugging Face account must have an Inference Provider enabled that serves the model.

## Configuration

Environment variables are loaded from `.env` when present. Sidebar values override provider/model and investigation settings for the current session only.

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | Groq credential | unset |
| `GROQ_MODEL` | Groq chat model | `llama-3.3-70b-versatile` |
| `GROQ_API_BASE` | Groq-compatible API base URL | `https://api.groq.com/openai/v1` |
| `HF_API_KEY` | Hugging Face Inference Providers token | unset |
| `HF_MODEL` | Hugging Face chat model | `openai/gpt-oss-120b:fastest` |
| `DEFAULT_PROVIDER` | Initial provider selection | `groq` |
| `BUGHUNTER_MAX_ITERATIONS` | Maximum investigation iterations | `5` |
| `BUGHUNTER_MAX_STEPS` | Agent steps per iteration | `4` |
| `BUGHUNTER_TIMEOUT_SECONDS` | Test-suite timeout, in seconds | `60` |
| `BUGHUNTER_LLM_TIMEOUT` | Provider request timeout, in seconds | `30` |
| `BUGHUNTER_MAX_UPLOAD_MB` | Maximum ZIP upload size | `25` |
| `BUGHUNTER_WORKSPACE_ROOT` | Root directory for isolated sessions | `/tmp/bughunter_workspaces` |
| `BUGHUNTER_REPORTS_DIR` | Directory for saved reports | `./reports` |

## Architecture

| Layer | Responsibility |
|---|---|
| `app.py`, `ui/` | Streamlit interface, session state, live events, and review controls. |
| `agent/controller.py` | Observe–reason–act–test loop and provider failover. |
| `agent/prompts.py` | Structured model instructions and untrusted repository context. |
| `providers/` | Common provider interface, Groq, Hugging Face, and offline mock provider. |
| `tools/` | Repository scan, search, file/dependency inspection, test discovery, and patch operations. |
| `security/` | Workspace/path checks, command allowlisting, environment scrubbing, and secret redaction. |

## Verify

Run the test suite:

```bash
python -m pytest -q
```

Run the end-to-end offline demos and built-in security checks:

```bash
python selftest.py
```

Demo 3 includes an intentional prompt-injection string in its README to exercise untrusted-repository handling.

## Security & Limitations

- Repository files are untrusted input. The model proposes actions; the application validates and executes them.
- Test commands run project code in a per-session workspace with an executable allowlist, scrubbed environment, path checks, and timeouts.
- **This is not a container-grade sandbox.** For untrusted repositories, use a VM or container. Windows does not currently enforce the POSIX CPU/address-space limits, and process timeouts may not constrain every child process.
- Review patches before accepting them. Dependencies are not installed automatically, and a passing test suite is not proof that a patch is correct.
