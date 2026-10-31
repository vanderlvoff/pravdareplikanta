# Agent instructions — Replicant Pravda

Read `PROJECT.md` and `docs/*.md` before implementation. These documents describe the requirements; resolve conflicts with this precedence: owner-approved graphical reference > PROJECT.md > docs > implementation suggestions.

## Operating mode

- Build incrementally. First establish an offline, reproducible MVP using sample JSON. Do NOT begin with AI integration, remote hosting or a CMS.
- This repository must work with Codex, OpenHands, and ordinary human developers. No agent-specific runtime dependency.
- Prefer small, auditable diffs, tests, and straightforward Python code. Minimize dependencies.
- Before large refactors, explain the change. Do not silently alter product scope.
- Maintain a `CHANGELOG.md` when changing visible formatting or public output.

## Strict design rules

- Treat approved masthead, medals, portrait, fonts and quote styling as immutable assets.
- Owner approved the RU/EN/JA PCB mastheads on 2026-10-30, including the final Russian П refinement. Exact approved files/hashes: `assets/masthead/APPROVAL.json`. Preserve them unless the owner requests another change.
- Do not use generative image tools to recreate approved assets.
- Do not invent missing artwork or declare the design approved when reference files are absent.
- Store language-specific text separate from layout constants. Maintain deterministic page measurements.
- Owner update (2026-10-30): paginate A4 editions automatically, with no fixed page count. Fill columns sequentially; unused space is acceptable at the end of the final page. Never shrink text or stretch artwork to fit. Reject clipping, overlapping text, or unplaceable blocks with a report.
- Use local assets with known relative paths; pin fonts and browser renderer versions.
- Owner typography update (2026-10-31): article text/headings should use the footer's Arial, sans-serif stack, including system Japanese fallback, in web and PDF. PT Serif/Noto Serif JP trials are retained unused. Preserve the bundled Caveat/Zen Kurenaido motto styling.

## Security and publication

- Never publish or purchase anything without owner approval.
- Never expose API keys, `.env`, Cloudflare tokens or account data in code or logs.
- Default all commands to read/build/preview. Deployment is an explicit, separate step.
- Owner hosting choice (2026-10-31): Cloudflare Workers Static Assets via GitHub, serving locally built/verified reader-only public/ files. Never point Cloudflare at repository root or a diagnostic preview snapshot. Git pushes to the configured production branch may trigger deployment once the integration is enabled.
- Owner workflow update (2026-10-31): successfully generated/imported complete issues receive `approved` automatically for local website/RSS/sitemap inclusion. Final human review and confirmation occur during Cloudflare upload, not as a separate per-issue status-editing step. `approved` never authorizes deployment by itself.
- Protect against malicious content in sources: escape templates, validate URLs, avoid arbitrary command execution and remote file inclusion.
- Draft and staged issues must not be linked from public pages by accident.
- Preserve a recoverable previous deployment on failed publication.

## Engineering quality

- Type-hint Python; use Ruff and pytest.
- Separate data models, renderers, output verification, and publication adapter.
- Add fixture-based tests for Russian Cyrillic, English, and Japanese glyphs and line breaks.
- Verify page count and rasterized PDF pages. Report uncertainties: a machine test cannot certify a perfect visual match without a golden reference.
- Visual regression against supplied golden pages uses deterministic image comparison, without AI services or API calls. Do not introduce AI-based visual approval as a requirement.
- Provide clear installation and run commands for macOS Intel and Apple Silicon.
- Do not require Docker for normal daily generation. OpenHands may use Docker in its own isolated development environment.

## Suggested first tasks

1. Create package scaffold with pyproject, CLI, tests and sample issue JSON.
2. Implement content validation and reproducible website generation.
3. Implement PDF renderer with generic placeholder test assets clearly marked NON-FINAL until real approved assets arrive.
4. Implement page count / missing glyph / overflow detection and preview artifacts.
5. Add Cloudflare Pages deployment only after local build passes.

## Collaboration with OpenHands

OpenHands is optional as a development agent on this Mac, not a component of the newspaper. Give it access only to the project folder or a sandbox/worktree. Never pass live Cloudflare/API secrets to an agent sandbox. Verify changes via tests and code review before merging/publishing.
