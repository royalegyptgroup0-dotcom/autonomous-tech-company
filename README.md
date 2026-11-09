# Independent Technology Company

An independent technology-company foundation focused on software engineering, intelligent automation, digital infrastructure and applied AI.

## Website
The responsive company website is maintained in `web/`:
- `index.html` — English company landing page
- `ar/index.html` — Arabic company landing page (RTL)
- `styles.css` and `ar/ar.css` — responsive visual system and Arabic layout
- `app.js` — accessible mobile navigation
- `favicon.svg` — lightweight neutral favicon

The website intentionally uses a descriptive identity rather than an unapproved company name. Official business contact details are not published until the legal/commercial identity and business email are confirmed.

## Principles
- Free and open-source first; no new paid service without explicit approval.
- Independent ownership, operations, infrastructure, data, and identity.
- Human approval for contracts, payments, financial commitments, legal obligations, and sensitive access changes.
- Security, auditability, least privilege, and measurable delivery.
- Validate customer demand before building a large platform.
- Never claim customers, certifications, capabilities, or production deployments that have not been verified.

## Initial stack
- Python + FastAPI
- pytest
- Static HTML/CSS/JavaScript website
- GitHub Actions for tests

## Local development
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests with `pytest -q`.

## Project status
The public website is deployed on Cloudflare Pages: https://autonomous-tech-company.pages.dev (English) and https://autonomous-tech-company.pages.dev/ar/ (Arabic). The production branch is `main`; the Pages project uses `web/` as its root directory and has no build command. Hosting currently uses the free `pages.dev` subdomain. A custom domain, business email and customer-intake backend are not configured. The company name remains provisional and is not represented as a registered or legally cleared trademark.

## Local engineering review agent (Phase 1)

A Windows-native, local-first review agent is being developed in a separate draft pull request. It uses Ollama on loopback only, reads enabled Git repositories, and stores reports/logs locally. It does not edit source code, run arbitrary commands, push changes, merge pull requests, or deploy.

- Implementation and setup: [docs/LOCAL_AGENT.md](docs/LOCAL_AGENT.md)
- Read-only Windows hardware/tool preflight: [scripts/Test-LocalAgentPrerequisites.ps1](scripts/Test-LocalAgentPrerequisites.ps1)
- Example configuration: [config/agent.example.json](config/agent.example.json)
- Engineering work is on branch `feature/local-autonomous-engineering-agent-2026-11-09`; the earlier [Pull request #1](https://github.com/royalegyptgroup0-dotcom/autonomous-tech-company/pull/1) is closed without merge.
- CI validation: the initial implementation and follow-up symlink regression test passed on Ubuntu and Windows, including PowerShell syntax checks.
- Local Windows + Ollama smoke test is still required before enabling the agent or registering its scheduled task.

The example config intentionally has all projects disabled and blank paths. Run the preflight before downloading a local model, then configure only verified local repository roots before running the agent. Real Windows + Ollama inference remains a manual release gate.

## Next milestones
See `docs/ROADMAP.md` and `docs/REVENUE_PLAN.md`.
