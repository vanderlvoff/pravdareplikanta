# Replicant Pravda

Offline Phase 1 scaffold: strict editorial JSON, RU/EN/JA static website previews,
and a local preview server. No API accounts, Docker, Node or secrets required for daily use.
Read PROJECT.md and docs/ for the full product requirements.

## Setup on macOS (Intel or Apple Silicon)

Install native Python 3.12 or newer using the python.org macOS universal2 installer.
Use the same commands on either architecture:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
rp validate content/issues/2026-10-29.json
rp build --issue 2026-10-29 --output dist
rp preview --output dist
```

Open http://127.0.0.1:8000. Stop with Ctrl-C. Builds require no network after
installation. Existing output is never overwritten: use a fresh output directory
for each subsequent build, for example `--output previews/revision-2`.

```sh
pytest
ruff check .
ruff format --check .
```

## Scope and review

The sample is a fictional editorial exercise with an explicitly marked placeholder
citation, not reporting. All output is a NON-FINAL local review snapshot, including
drafts; do not upload it to public hosting. Robots directives discourage indexing
but are not access control. Internal editorial notes currently appear in this local
review output. Publication is not implemented.

The generic screen layout uses browser fonts. Approved artwork, bundled fonts,
Japanese name and golden references are still required. Unicode and explicit
line-break preservation are tested; actual font glyph rendering is not yet verified.
Images are intentionally rejected until reviewed asset and licensing handling exists.

Phase 2 will add pinned Chromium, exactly three A4 PDF pages per language, font and
asset checks, overflow reports and raster previews. `verification.json` currently
records unavailable checks; it is not a certification. Phase 3 will add public-only
snapshots, canonical URLs, hreflang metadata, RSS, sitemap, historical archive
aggregation, verification and an owner-approved deployment adapter. Current archive
pages list only the selected issue. No `verify` or `publish` command exists yet.

## Version control

Canonical JSON and source belong in Git; generated snapshots and secrets are ignored.
The intended remote is https://github.com/vanderlvoff/pravdareplikanta.git.
Source pushes and public site deployment are separate operations.
