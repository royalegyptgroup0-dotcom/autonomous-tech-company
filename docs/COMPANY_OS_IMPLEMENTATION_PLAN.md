# Company OS Implementation Plan

## Verified baseline
- Public website exists under `web/` with English and Arabic RTL pages and a Cloudflare Pages deployment on the free `pages.dev` hostname.
- FastAPI currently exposes only `GET /` and `GET /health`; it does not accept customer data.
- GitHub Actions runs Python tests and navigation tests on Ubuntu and Windows.
- Local engineering review Phase 1 is Windows/Ollama-based and read-only. The actual Windows + Ollama smoke test remains a manual gate.
- The business-agent suite is defined as local OpenCode profiles; it is not a live autonomous service.

## Phase A — public website and UX
1. Audit actual user journeys, current copy, SEO, accessibility and responsive behavior.
2. Keep the company identity descriptive/provisional until a name is approved and legally checked.
3. Improve project-specific design tokens, hierarchy, Arabic/English parity, mobile layouts, accessibility, SEO and performance on an isolated branch.
4. Do not publish unverified capabilities, clients, certifications, prices or testimonials.
5. Do not enable customer intake until a real endpoint, privacy notice and secure handling are implemented.
6. Require browser screenshots at 360, 768, 1024 and 1440 CSS pixels before visual QA is called complete.

## Phase B — local specialist agents
- Profiles cover strategy, operations, finance, market research, lead generation, sales, support, proposals, architecture, development, QA, DevOps, security, product research, product management, SaaS engineering and documentation.
- The Web Design Director profile is proposed separately in PR #20.
- Configure OpenCode for local Ollama only and benchmark the installed model before changing model size/context.
- Keep edits and shell commands approval-gated. No unattended external actions.

## Phase C — Company OS control plane
Implement incrementally with tests:
1. Agent registry and capability metadata.
2. Task intake with schema validation, project scope, priority and ownership.
3. Local SQLite development store; design a migration path before hosted persistence.
4. Approval inbox and explicit, scoped action grants.
5. Append-only audit events and task/run state transitions.
6. Orchestrator dispatching only to registered profiles with bounded context and tool allowlists.
7. Idempotency keys, retry budgets, cancellation, stale-task recovery and kill switch.
8. Authenticated dashboard with role-based access; no public admin endpoints.
9. Backup/restore and incident runbooks.
10. Integration tests for project isolation, permissions, audit completeness and recovery.

## Phase D — bounded automation
- Start recommendation-only.
- Allow local reversible actions only after tests and separate security review.
- Draft-only pull requests are the first software delivery action.
- Production deployment, outbound messages, customer-data changes, financial/legal actions, account changes and paid services require explicit owner approval.

## Cost policy
Target recurring cost is $0. Prefer the existing static hosting, local Ollama, OpenCode, SQLite, Python/FastAPI, GitHub Actions and open-source libraries. Check free-tier quotas and data handling before relying on a service. Do not add metered cloud inference, paid design credits, paid automation, custom domains, email hosting or billing without approval.

## Definition of done
A component is complete only when code exists, automated tests pass, relevant manual/browser checks are recorded, security boundaries are reviewed, documentation matches behavior, and deployment state is identified. A role profile or mockup is not a live agent or Company OS.
