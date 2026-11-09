# Local Autonomous Engineering Agent — Phase 1

## Goal

A free-first, Windows-native, local agent that remains available while the PC is powered on and the user is logged in. It uses Ollama on localhost; no paid model API, cloud inference, FastAPI, Docker, or external agent service is required.

## Hardware profile

Measured target: Windows, 15.31 GiB physical RAM, AMD Ryzen 5 PRO 5650U (6 cores / 12 threads), integrated AMD Radeon Graphics (reported adapter memory 512 MiB). The installed local model is qwen2.5:3b. Two user-run CLI tests took 59.4 s and 94.7 s; these timings include prompt processing and output generation and are not tokens/second benchmarks. `ollama ps` reported 100% CPU, 2.2 GB model memory, and context 4096. Therefore Phase 1 defaults to qwen2.5:3b, a 4096-token context, and a 300-second request timeout; process one repository at a time and do not download larger models until measured throughput and available memory justify it. GPU acceleration is not assumed. See the [Ollama model library](https://ollama.com/library/qwen3.5) and [official Qwen model card/license](https://huggingface.co/Qwen/Qwen3.5-4B). Ollama runs natively on Windows and exposes its local API at http://127.0.0.1:11434. The agent accepts only plain-HTTP loopback IP addresses (127.0.0.1 or ::1) and rejects redirects; remote inference endpoints and hostname-based URLs are intentionally unsupported.

## Phase 1 delivered here

- Per-project registry with separate repository roots and IDs.
- Read-only Git status/history and bounded repository snapshot collection.
- Local Ollama inference only; proxy environment variables are ignored, redirects are refused, and only loopback IP literals are accepted.
- Periodic review cycle with independent failure handling per project.
- SQLite run history, local Markdown reports, and size-limited rotating logs under `.local-agent/logs/`.
- Windows Task Scheduler launcher with restart-on-failure settings.
- Read-only prerequisite script checks Git, Python, Ollama, physical RAM, free disk, and installed Ollama models without installing or downloading anything.
- No arbitrary shell execution, file edits, commits, pushes, merges, deployment, or secret collection.

## Setup

1. Run the read-only hardware/tool check in PowerShell: `powershell -NoProfile -File scripts/Test-LocalAgentPrerequisites.ps1`. It does not install software, download models, or change settings.
2. Review available RAM and free disk. Install Ollama for Windows only if it is not already installed: https://ollama.com/download/windows.
3. Choose an appropriately sized local model. The default is `qwen2.5:3b`, matching the model already installed on the measured target PC. No model download is needed for the initial run. Keep the context at 4096 unless a measured task requires more. Model downloads use internet bandwidth and local disk, but do not require a paid model API.
4. Copy `config/agent.example.json` to `config/agent.local.json`.
5. The example config intentionally ships with every project disabled and every path blank. Add exact local repository paths and enable only roots you have personally verified. Each project must be a separate, non-overlapping Git root; never leave a guessed or stale path enabled. Add source files to that project's `review_files` list only after checking that they contain no passwords, API keys, personal data, or other secrets. The agent reads only those explicitly listed source files plus its small built-in documentation/manifest allowlist.
6. Run: `python local_agent/engine.py --config config/agent.local.json --check` (validates configuration and the local model without creating the database or reports).
7. Run one test review: `python local_agent/engine.py --config config/agent.local.json --once`.
8. Inspect reports under `.local-agent/reports/`.
9. Inspect `.local-agent/logs/agent.log` if the scheduled run reports errors; logs rotate at 2 MB with three backups.
10. Only after the one-time review succeeds and its local report is inspected, optionally install the logon task: `powershell -ExecutionPolicy Bypass -File scripts/Install-LocalAgentTask.ps1`.

The first run of the task installer creates the private local config if missing; edit and run the installer again to register it. The task runs in the signed-in user's session. It cannot run while the PC is powered off, sleeping, or the user is signed out.

## Phase 2 — bounded code changes

Not enabled in Phase 1. It will add a separate worktree/branch per repository, a strict patch parser, path and symlink validation, an allowlisted test runner, rollback on failed tests, and draft-only pull requests. The model will never receive arbitrary shell execution. Production, credentials, billing, legal, deletion, publishing, firewall/WFP, and external side effects remain approval-gated.

## Phase 3 — continuous operations

Add issue/task intake, watchdog/heartbeat, retry budgets, stale-task recovery, report rotation, and per-project schedules. Network and power interruptions are handled by restart/retry, not described as uninterrupted uptime.

## Data boundaries

The local agent reads only enabled repository roots and writes only to its .local-agent workspace. It does not read .env, private keys, credential files, or arbitrary home-directory content. Project reports remain local and are not uploaded automatically.
