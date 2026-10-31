# MVP delivery plan

## Phase 0 — Inputs & baseline
- [ ] Owner supplies actual approved masthead/medals/portrait/font files, and a sample issue PDF (RU and EN; JA if available).
- [ ] Record names, file checksums and permitted usage.
- [ ] Confirm Mac architecture, Python tooling, Node tooling.

## Phase 1 — Minimal build without AI
- [x] Python package scaffold and CLI.
- [x] Validated example JSON issue with RU/EN/JA fixtures.
- [x] Jinja2 responsive website with archive pages, per-article links and language routes.
- [x] Historical issue aggregation with a localized archive index, dated article routes and PDF verification; see [ARCHIVE.md](ARCHIVE.md).
- [x] RU/EN/JA RSS, eligible-page sitemap, canonical and reciprocal hreflang; see [DISCOVERY.md](DISCOVERY.md). Public indexing remains disabled for previews.
- [x] Local preview of generated snapshots and unit tests.

## Phase 2 — Printable newspaper
- [x] Provisional print CSS for automatically paginated A4 editions, with clipping/overlap rejection.
- [x] Pinned Chromium/Playwright renderer and bundled Caveat quotation font.
- [x] Owner-selected article typography matches the footer’s Arial/sans-serif stack, with actual browser usage/PDF embedding checks. Serif trial assets are retained unused; motto fonts stay bundled.
- [x] Asset integrity checks and PDF/page preview checks.
- [ ] Golden reference approval and algorithmic image comparison for each locale; no AI service required.

## Phase 3 — Publishing
- [x] Local publication proofs and reader-only release packaging with checksum validation.
- [x] GitHub/Cloudflare Workers Static Assets configuration and pinned Wrangler; live deployment awaits dashboard confirmation.
- [ ] Custom domain and HTTPS after owner registration.
- [x] Rollback and local snapshot backup workflow documented.

## Phase 4 — Automated editorial features
- [x] API issue generation with researched sources and local validation; live editorial quality remains to be evaluated.
- [ ] Translation review and hallucination checks.
- [x] Owner-authorized macOS launchd publication at 06:20 JST; isolated build/check/commit/main push, with post-deployment Telegram announcement. See [DAILY_PUBLICATION.md](DAILY_PUBLICATION.md).
- [ ] Final human review/confirmation integrated into Cloudflare upload. Generated/imported complete issues receive approved status automatically.

## Future, outside MVP
- [ ] Optional OpenHands agent development workflows.
- [ ] Local editor UI / CMS.
- [ ] Social preview cards, mailing list, reader analytics, search.
- [ ] Optional automatic print to Brother printer.

## Start prompt for Codex/OpenHands

> Read AGENTS.md, PROJECT.md and docs/*.md. Implement Phase 1 only: a reproducible Python package, JSON issue schema, CLI for `validate` and `build`, responsive Jinja2 templates for RU/EN/JA and pytest fixtures. Do not publish, register accounts or introduce AI APIs. Use clearly labeled placeholder assets until the owner provides approved graphics. Report commands to run locally and what tests passed.
