# Autonomous Technology Company

An independent, AI-first software and automation company foundation. The company is designed to deliver practical AI, automation, and software services first, then productize proven solutions into reusable products.

## Principles
- Free and open-source first; no new paid service without explicit approval.
- Independent ownership, operations, infrastructure, data, and identity.
- Human approval for contracts, payments, financial commitments, legal obligations, and sensitive access changes.
- Security, auditability, least privilege, and measurable delivery.
- Validate customer demand before building a large platform.

## Initial stack
- Python + FastAPI
- pytest
- Static HTML/CSS/JavaScript landing page
- GitHub Actions for tests

## Local development
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests with `pytest`.

## Project status
Foundation scaffold only. No production deployment, customer data, paid services, or external integrations are configured.

## Next milestones
See `docs/ROADMAP.md` and `docs/REVENUE_PLAN.md`.
