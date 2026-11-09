# Royal Egypt Group Source Review Boundary

The source repository is `royalegyptgroup0-dotcom/Royal-Egypt-Group` (default branch `main`). Its README describes a static group portal with properties, coffee and transportation pages, shared CSS/JS, Cloudflare Pages functions and a D1-backed intake/listings workflow.

Potentially reusable *ideas* after detailed review:
- Responsive navigation and language-switching patterns
- Accessible form UX
- Static page composition and CSS tokens
- General-purpose validation and test patterns, rewritten independently

Do not copy into this company:
- Royal Egypt brand assets, logo, names, copy or sector-specific content
- Listings, customer/contact data, enquiries, phone numbers or email addresses
- D1 IDs, Cloudflare bindings, secrets, analytics tokens, webhook URLs or environment config
- Royal Egypt production routes, domain settings or deployment configuration
- Any file whose ownership/licensing or sensitive-data status has not been established

Current decision: build a clean scaffold first. Review selected public-facing components individually before considering any code reuse. No changes have been made to the source repository or its production environment.
