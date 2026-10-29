# MVP delivery plan

## Phase 0 — Inputs & baseline
- [ ] Owner supplies actual approved masthead/medals/portrait/font files, and a sample issue PDF (RU and EN; JA if available).
- [ ] Record names, file checksums and permitted usage.
- [ ] Confirm Mac architecture, Python tooling, Node tooling.

## Phase 1 — Minimal build without AI
- [x] Python package scaffold and CLI.
- [x] Validated example JSON issue with RU/EN/JA fixtures.
- [x] Jinja2 responsive website with archive pages, per-article links and language routes.
- [x] Local preview of generated snapshots and unit tests.

## Phase 2 — Printable newspaper
- [x] Provisional print CSS for precisely three A4 pages, with overflow rejection.
- [x] Pinned Chromium/Playwright renderer and bundled Caveat quotation font.
- [ ] Approved bundled article and Japanese quotation fonts (currently deferred by owner).
- [x] Asset integrity checks and PDF/page preview checks.
- [ ] Golden reference approval for each locale.

## Phase 3 — Publishing
- [ ] Cloudflare Pages Direct Upload test environment.
- [ ] `publish --confirm` with validation gate and clear deployment report.
- [ ] Custom domain and HTTPS after owner registration.
- [ ] Rollback and backup documentation.

## Phase 4 — Automated editorial features
- [ ] AI-assisted drafting pipeline from vetted sources with source metadata.
- [ ] Translation review and hallucination checks.
- [ ] Optional macOS launchd schedules.
- [ ] Human-in-the-loop approval before public release.

## Future, outside MVP
- [ ] Optional OpenHands agent development workflows.
- [ ] Local editor UI / CMS.
- [ ] Social preview cards, mailing list, reader analytics, search.
- [ ] Optional automatic print to Brother printer.

## Start prompt for Codex/OpenHands

> Read AGENTS.md, PROJECT.md and docs/*.md. Implement Phase 1 only: a reproducible Python package, JSON issue schema, CLI for `validate` and `build`, responsive Jinja2 templates for RU/EN/JA and pytest fixtures. Do not publish, register accounts or introduce AI APIs. Use clearly labeled placeholder assets until the owner provides approved graphics. Report commands to run locally and what tests passed.
