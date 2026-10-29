# Replicant Pravda — Project Specification

Version: 0.1 (2026-10-29)  
Status: development handoff / MVP specification

## 1. Product vision

Create a public, multilingual internet newspaper about Physical AI, titled **Правда репликанта / The Replicant Truth** (Japanese display name to be approved). Target domain: `replicantpravda.com` (registration and availability NOT confirmed).

The newspaper has two distinct outputs built from a **single editorial dataset**:

1. A responsive public website with news articles, issue archive, language navigation, permanent URLs and RSS.
2. A print-ready newspaper PDF: **exactly three A4 pages per language** (RU, EN, JA), designed in the established Soviet *Pravda*-inspired newspaper style.

The masthead and its adornments must preserve the user's **already approved design**. Do NOT redesign or regenerate it based on a prose description. Approved assets must be explicitly supplied before finalizing the newspaper visuals.

## 2. Final architecture decision

**Local-first publishing from the user's Mac.** No VPS, shared hosting, PHP, PythonAnywhere, permanent remote backend, or GitHub Actions required for the MVP.

- On macOS: Python application, Jinja2 HTML templates, CSS, Playwright/Chromium for print output (replaceable renderer), SQLite for local editorial state, file-based assets, tests.
- Publication: static site generator outputs an immutable `dist/` directory; upload build to Cloudflare Pages via Wrangler Direct Upload.
- Cloudflare hosts only static HTML/CSS/JS/images/PDF/RSS; it does not generate issues or need API access to the model.
- Domain and DNS configured separately by owner. Do not assume it has been purchased.
- Local scheduler may be added later via macOS `launchd`; manual `build`, `verify`, and `publish` commands must work first.

**Agentic development tools:** Codex in VS Code is the default implementation workflow; OpenHands is optional. Neither must be a runtime dependency for publishing.

## 3. Editorial scope

- Subject matter: Physical AI, humanoids, VLA, embodied foundation models, robotics manipulation, deployment, engineering, commercial viability and safety.
- Languages: Russian, English, Japanese. Maintain parallel edition/issue IDs, but allow editorially correct translations rather than literal word-for-word translation.
- Distinguish news, analysis, opinion, and satire. Every news claim should be traceable to a cited source URL and publication date. Do not fabricate sources.
- A future AI editorial pipeline may generate drafts via external APIs. MVP should first accept **manually supplied validated JSON**; no AI subscription or API key necessary to build the first issue.
- Human review gate before public publication, even if automated checks pass.
- Corrected editions must be labeled with revision timestamps; keep original source JSON version history in Git.

## 4. Immutable brand requirements

- Print PDF must use the exact previously approved masthead composition, not an image generated anew.
- Roy Batty portrait, three medals (Orion Falcon, Defense of Jupiter, Hero of Tannhäuser), typography, borders, offsets and alignment must come from approved files. Medals' inscriptions must match edition language where approved variants exist.
- Fonts, including user-supplied Caveat-Regular for quotations, must be bundled inside the project and embedded in exported PDFs where licensing permits.
- Do not download, substitute, redraw, restyle, stretch, crop, or reflow approved assets without explicit approval.
- Use visual regression image comparisons of PDF pages against a user-approved golden reference. If references are not supplied, mark visual approval BLOCKED; do not claim fidelity.
- Explicitly test masthead right edge, medal alignment, portrait proportion, weather block, and quote font. These are known regression-sensitive elements.

## 5. MVP features

### Reader-facing
- Responsive landing page with latest issue and article links.
- Localized routes `/ru/`, `/en/`, `/ja/`; individual issues `/ru/issues/YYYY-MM-DD/`, etc.; articles `/ru/articles/<slug>/`.
- Link to PDF edition for each language, visible issue date/number and source citations.
- Archive index, RSS feed per language, sitemap, canonical and hreflang tags, robots.txt.
- Mobile-friendly layout and accessible semantics.

### Editorial/build
- Import and validate editorial JSON against schema.
- Render website and three paper PDFs from common content; separate screen and print CSS layouts are permitted.
- Fail loudly if fonts/images missing, schema invalid, pages are not exactly 3, or pages have clipped content.
- Produce preview images and a validation report before publication.
- Atomic-style publication of a whole `dist/` snapshot; do not overwrite live site on failed build.
- Local SQLite for optional drafts and publishing metadata; avoid needless backend complexity.

### Exclusions from MVP
- Public login, comments, subscriptions/paywalls, online editing, payments, advanced site search, remote API, always-on server, OpenHands runtime, autonomous publication without review.

## 6. Technical stack

- Python 3.12+ with `uv` or standard `venv` for dependency management.
- Jinja2; Pydantic or JSON Schema for validation.
- Playwright and pinned Chromium browser version for PDF generation; evaluate WeasyPrint only if needed, with output tests.
- PyMuPDF/pypdf for page-count and text-bound checks; page raster previews for visual review.
- SQLite (stdlib) for local metadata, JSON source files in Git as canonical portable edition input.
- Node.js and Cloudflare Wrangler CLI for deploy only. Pin tooling versions.
- pytest; Ruff; optional visual snapshot tooling.
- Git and `.env` for local secrets; **never commit API keys, cookies or credentials**.

## 7. Suggested repository structure

```text
replicant-pravda/
├── AGENTS.md
├── PROJECT.md
├── docs/
│   ├── CONTENT_SCHEMA.md
│   ├── DESIGN_AND_QA.md
│   ├── DEPLOYMENT.md
│   └── ROADMAP.md
├── assets/
│   ├── fonts/              # approved font files copied by owner
│   ├── medals/             # approved variants copied by owner
│   ├── masthead/           # approved portrait/header copied by owner
│   └── images/
├── content/
│   └── issues/
├── templates/
│   ├── web/
│   └── print/
├── src/replicantpravda/
├── tests/
├── scripts/
├── dist/                   # generated, ignored from git by default
├── previews/               # generated
├── pyproject.toml
└── .env.example
```

## 8. Command-line contract (to implement)

```shell
rp validate content/issues/2026-10-29.json
rp build --issue 2026-10-29 --output dist
rp verify --issue 2026-10-29 --output dist
rp preview --issue 2026-10-29
rp publish --output dist --confirm
```

These commands are **design targets**, not existing code. Publishing must require explicit confirmation; optional automation can later be enabled through clearly configured policy.

## 9. Definition of done for MVP

1. Fresh clone can install dependencies and build demo content on a Mac.
2. A sample issue renders all three localized website editions and 3-page A4 PDFs.
3. Each PDF reports 3 pages; no clipped text, missing glyphs or missing assets.
4. Approved masthead visual regression passes once source assets and golden reference are received.
5. Local preview serves static pages and PDF without any external backend.
6. Deployment script can publish `dist/` to an operator-owned Cloudflare Pages project.
7. A failed validation cannot trigger publication.
8. Setup and recovery are documented; secrets remain out of Git.

## 10. Pending inputs — do not guess

- Owner must supply approved fonts, portrait, medals, masthead reference and sample PDFs. Files may currently be in ChatGPT Library and are not automatically available to Codex.
- Domain purchase and Cloudflare Pages project creation are not completed.
- Japanese publication name and translation/style policies require final editorial approval.
- Exact print spacing, typography measurements and existing issue numbering derive from the final approved sample, not this spec.
- API provider/model, usage budgets and publishing schedule to be decided separately.
