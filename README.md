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
The website source is maintained in this repository. A production website deployment, custom domain, business email, customer intake backend and paid services are not configured. Do not describe the site as publicly launched until a hosting deployment has been verified.

## Next milestones
See `docs/ROADMAP.md` and `docs/REVENUE_PLAN.md`.
