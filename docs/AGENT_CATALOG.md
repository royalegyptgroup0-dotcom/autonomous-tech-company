# Company Agent Catalog

The local agent suite is defined as reusable OpenCode profiles under `.opencode/agents/`. It is intended to run against the operator-configured local Ollama runtime; no paid hosted model or API is required by these profiles.

| Profile | Responsibility | Mode |
|---|---|---|
| company-orchestrator | Task intake, delegation, project boundaries and consolidated status | Primary |
| ceo | Strategy, objectives and decision briefs | Subagent |
| coo | Operations, procedures, delivery and KPIs | Subagent |
| cfo | Budgets, cash flow and unit economics | Subagent |
| market-research | Evidence-led market and competitor research | Subagent |
| lead-generation | Public prospect discovery and qualification | Subagent |
| sales | Discovery, qualification and sales enablement | Subagent |
| customer-support | Support triage, accurate replies and escalation | Subagent |
| proposal | Scoped proposals and statements of work | Subagent |
| software-architect | System architecture and technical decisions | Subagent |
| developer | Bounded implementation and focused tests | Subagent |
| qa-testing | Quality plans, regression and release evidence | Subagent |
| devops | CI, operations, backup and deployment planning | Subagent |
| security-reviewer | Threat modeling and defensive security review | Subagent |
| product-research | User needs and opportunity validation | Subagent |
| product-manager | Requirements, backlog and product outcomes | Subagent |
| saas-development | Tenant-aware SaaS engineering | Subagent |
| documentation | Verified documentation and handoffs | Subagent |
| web-design-director | UX, visual system, responsive implementation and design QA | Proposed separately in [PR #20](https://github.com/royalegyptgroup0-dotcom/autonomous-tech-company/pull/20) |

## Activation boundary
These files are role instructions, not proof of continuously running agents. OpenCode must be configured to use local Ollama, and the user/operator must start a session and choose the primary agent. Specialist delegation depends on the configured OpenCode runtime.

The FastAPI service currently has only health/root routes. A persistent Company OS orchestrator, agent registry API, task queue, approval inbox, audit log, durable memory and scheduler are not implemented yet. The separate `local_agent/` engineering reviewer is read-only and is not the business-agent runtime.

All profiles require approval for editing, shell commands, external-directory access and delegation. Human approval remains mandatory for spending, contracts, legal commitments, outreach, customer-data changes, destructive actions, production access, merge and deployment.

## Free-first runtime
- Use the already-installed local Ollama model when available; measured hardware notes are in `docs/LOCAL_AGENT.md`.
- Do not silently switch to hosted inference, paid APIs, design credits or metered providers.
- Keep prompts and reports local; do not include credentials or unnecessary personal data.
