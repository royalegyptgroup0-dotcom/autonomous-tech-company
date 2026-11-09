# Target Architecture

## Initial delivery
- Static public website (no build system required).
- FastAPI service for health and future API routes.
- Automated tests in GitHub Actions.
- No production database or customer-data intake in this scaffold.

## Planned modules (not yet implemented)
- Identity and access management
- Tenant-aware customer workspace
- CRM and lead pipeline
- Workflow engine and job queue
- Agent registry and orchestrator
- Company memory with provenance and retention controls
- Audit log and approval queue
- Usage, cost and revenue analytics
- Backup, restore and incident response

## Guardrails
- Separate dev, staging and production environments.
- Per-environment secrets; never commit secrets.
- No cross-tenant queries without enforced tenant scope.
- Idempotency keys for retried side effects.
- Agent tool allowlists and explicit budgets.
- Human approval for financial/legal/ownership actions.
- Kill switch, rate limits, observability and tested recovery.
- No autonomous deployment to production until a reviewed release pipeline exists.
