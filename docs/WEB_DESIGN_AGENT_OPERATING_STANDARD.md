# Cross-Project Web Design Operating Standard

## Purpose
A shared operating standard for the Web Design Director Agent. This document standardizes quality and execution while preserving the identity and data isolation of every project.

## Portfolio map and separation
| Project | Design boundary |
|---|---|
| Royal Egypt Group | Parent business identity; branches retain their own service focus |
| Royal Egypt Properties | Real-estate discovery, listing trust, lead capture and developer/investor journeys |
| Royal Egypt Coffee | Product/menu and service presentation; do not imply unavailable operations |
| Royal Egypt Transportation | Transport service information and booking/intake only where operationally supported |
| CEO Notes | Editorial reading experience; separate tone, identity and publishing approvals |
| OCTOPUSA | Product/technical identity; keep its own product UX and repo |
| RoyalMediaPlayer | Desktop application UI only when explicitly included in scope |
| Autonomous technology company | Independent technology-services identity and lead-generation journey |

This map is contextual, not permission to access all repositories or data. Inspect the target project before acting.

## Default design system principles
- Use project-specific brand tokens; never impose a universal palette or logo.
- Define typography, spacing, layout, border, elevation, motion and state tokens.
- Use semantic HTML and native browser capabilities before adding dependencies.
- Design for Arabic RTL and English LTR where the project supports both.
- Maintain responsive behavior at 360, 768, 1024 and 1440 CSS pixels.
- Meet WCAG 2.2 AA as the practical accessibility target.
- Optimize Core Web Vitals and preserve SEO/crawlability.
- Use real product copy and real capabilities. Never fabricate reviews, statistics, certifications, inventory, pricing, service availability or success claims.
- Ensure every form submits to a verified endpoint and communicates loading, success and error states.

## Release gates
1. **Discovery:** repository, brand, routes, user journeys, constraints and baseline captured.
2. **Design:** project-specific tokens, responsive components and content hierarchy reviewed.
3. **Implementation:** isolated branch, minimal dependency changes, no cross-project file or data reuse.
4. **Verification:** automated tests plus browser/screenshot review on supported viewports and languages.
5. **Delivery:** PR/preview, exact test evidence, open issues and rollback path documented.
6. **Release:** merge/deploy only after explicit authorization.

## Free-first stack
- OpenCode: reusable agent runner; source available and agent profiles can be stored globally.
- Ollama: local inference runtime; use a model already supported by the user's hardware.
- Penpot: open-source design/prototyping and design-system tool; cloud sign-up is free, while self-hosted Professional is free but requires Linux infrastructure and Docker.
- Existing repository framework, test runner, Cloudflare Pages/Workers and current CI take precedence over new tooling.
- Avoid paid hosted AI design credits as a required dependency.

## Acceptance evidence
A design task is complete only when the report identifies the target commit/PR, tests actually run, responsive/browser evidence actually captured, and any unverified item. A green CI run alone does not prove visual quality.
