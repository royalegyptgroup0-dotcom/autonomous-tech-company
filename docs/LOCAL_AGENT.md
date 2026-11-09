# Local Autonomous Engineering Agent — Phase 1

## Goal

A free-first, Windows-native, local agent that remains available while the PC is powered on and the user is logged in. It uses Ollama on localhost; no paid model API, cloud inference, FastAPI, Docker, or external agent service is required.

## Hardware profile

Initial target: Windows + 16 GB RAM, GPU unknown. Start with qwen3.5:4b (about 4 GB model download) and CPU fallback. This model is published under Apache-2.0. If CPU speed or available memory is insufficient, switch to qwen3.5:2b. Do not download a larger model until GPU/VRAM and available memory are checked. Ollama runs natively on Windows and exposes its local API at http://127.0.0.1:11434. The agent accepts only plain-HTTP loopback IP addresses (127.0.0.1 or ::1) and rejects redirects; remote inference endpoints and hostname-based URLs are intentionally unsupported.

## Phase 1 delivered here

- Per-project registry with separate repository roots and IDs.
- Read-only Git status/history and bounded repository snapshot collection.
- Local Ollama inference only; proxy environment variables are ignored, redirects are refused, and only loopback IP literals are accepted.
- Periodic review cycle with independent failure handling per project.
- SQLite run history, local Markdown reports, and size-limited rotating logs under `.local-agent/logs/`.
- Windows Task Scheduler launcher with restart-on-failure settings.
- No arbitrary shell execution, file edits, commits, pushes, merges, deployment, or secret collection.

## Setup

1. Install Ollama for Windows from https://ollama.com/download/windows.
2. In PowerShell, run: ollama pull qwen3.5:4b
3. Copy config/agent.example.json to config/agent.local.json.
4. The example config intentionally ships with every project disabled and every path blank. Add exact local repository paths and enable only roots you have personally verified. Each project must be a separate, non-overlapping Git root; never leave a guessed or stale path enabled.
5. Run: python local_agent/engine.py --config config/agent.local.json --check (validates configuration and the local model without creating the database or reports).
6. Run one test review: python local_agent/engine.py --config config/agent.local.json --once
7. Inspect reports under .local-agent/reports/.
8. Inspect `.local-agent/logs/agent.log` if the scheduled run reports errors; logs rotate at 2 MB with three backups.
9. Install the logon task: powershell -ExecutionPolicy Bypass -File scripts/Install-LocalAgentTask.ps1

The first run of the task installer creates the private local config if missing; edit and run the installer again to register it. The task runs in the signed-in user's session. It cannot run while the PC is powered off, sleeping, or the user is signed out.

## Phase 2 — bounded code changes

Not enabled in Phase 1. It will add a separate worktree/branch per repository, a strict patch parser, path and symlink validation, an allowlisted test runner, rollback on failed tests, and draft-only pull requests. The model will never receive arbitrary shell execution. Production, credentials, billing, legal, deletion, publishing, firewall/WFP, and external side effects remain approval-gated.

## Phase 3 — continuous operations

Add issue/task intake, watchdog/heartbeat, retry budgets, stale-task recovery, report rotation, and per-project schedules. Network and power interruptions are handled by restart/retry, not described as uninterrupted uptime.

## Data boundaries

The local agent reads only enabled repository roots and writes only to its .local-agent workspace. It does not read .env, private keys, credential files, or arbitrary home-directory content. Project reports remain local and are not uploaded automatically.
