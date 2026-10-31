# Replicant Pravda

Local development build: strict editorial JSON, RU/EN/JA static website previews,
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
citation, not reporting. Ordinary builds are local NON-FINAL review snapshots,
including explicitly selected drafts; do not upload those snapshots to public hosting.
Use --publication and rp release to prepare the verified reader-only public/ folder
for GitHub/Cloudflare. Full source/diagnostic snapshots remain local. See deployment
instructions below; upload confirmation remains a separate step.

The screen preview uses the supplied SVG mastheads, medals and portrait unchanged.
Quotations use bundled Caveat-Regular; Russian quotation text comes from the header
reference. EN quotation is included; JA quotation uses owner-supplied wording.
Article text and headings use the footer’s Arial/sans-serif stack, including
system Japanese fallback, by owner preference. See [typography notes](docs/TYPOGRAPHY.md). Full-page golden references
and visual approval are still required. Unicode and explicit line-break preservation
are tested; RU/EN quotation font usage is also checked in Chrome.
Daily v1.3 feeds support two owner-supplied generated editorial WebP illustrations
per language. Images are copied from local `data/images/` with localized captions
and alt text; builds never include remote files. See [daily import](docs/DAILY_IMPORT.md).

Local PDF support now generates as many A4 pages per language as needed, with clipping/overlap
checks, embedded Caveat, raster previews and snapshot verification. See
[docs/PRINT.md](docs/PRINT.md) for installation, commands and current limitations.
The sample has three short fictional articles, so print pages are intentionally sparse.
Full-page references and visual approval remain pending.
The localized site archive supports explicitly selected historical issues and their
articles/PDFs. See [archive documentation](docs/ARCHIVE.md).
RU/EN/JA RSS, canonical/hreflang metadata and an approved-content sitemap are
implemented; see [docs/DISCOVERY.md](docs/DISCOVERY.md). Publication proofs and a
reader-only GitHub/Cloudflare release bundle are implemented; actual uploads require review.

## Cloudflare through GitHub

The current hosting setup uses Workers Static Assets, serving the locally prepared
`public/` directory. PDF rendering remains on the Mac. Cloudflare settings:

| Field | Value |
|---|---|
| Application name | `pravdareplikanta` |
| Production branch | `main` |
| Build command | `npm run check:public` |
| Deploy command | `npx wrangler deploy` |
| Root directory | repository root |
| Environment variable | `NODE_VERSION=22.16.0` |

Full instructions, local release commands and rollback:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). After enabling Git integration, pushes
to the production branch trigger deployment; review the release before pushing.

## RSS and search metadata

The owner-selected origin is `https://repravda.com`; override it with
`rp build ... --site-url http://127.0.0.1:8000` for local URL checks.
Each language has `/ru/rss.xml`, `/en/rss.xml` or `/ja/rss.xml`, with a footer
subscription link. RSS and sitemap include only approved/published issues.
Complete generated/imported issues receive approved status automatically; final
human review/confirmation happens during Cloudflare upload. The current October
30/31 issues are included in the feeds and sitemap. Explicit unfinished drafts
remain excluded. Preview robots/noindex rules remain in place.

## Site archive

The current archive includes October 30 and 31 in RU/EN/JA:

```sh
rp build --issue 2026-10-31 --content-dir content/technical \
  --archive-issue content/technical/2026-10-30.json \
  --pdf --output previews/archive-2026-10-31-8
rp verify --issue 2026-10-31 --output previews/archive-2026-10-31-8
rp preview --output previews/archive-2026-10-31-8
```

Open http://127.0.0.1:8000/ru/archive/ (also `/en/archive/`, `/ja/archive/`).
Repeat `--archive-issue PATH` to include another normalized issue. Without it,
the archive lists only the current issue. Historical drafts are never discovered
automatically. This remains a local review snapshot, with publication disabled.

## Local PDF proof

```sh
python -m pip install -e '.[pdf]'
python -m playwright install chromium --only-shell
rp build --issue 2026-10-29 --pdf --output previews/print-review
rp verify --issue 2026-10-29 --output previews/print-review
rp preview --output previews/print-review
```

The generated proof from development is at `previews/print-3`. Its localized pages
link to the PDFs. Stop an old server before serving a different output directory.

## Version control

Canonical JSON and source belong in Git; generated snapshots and secrets are ignored.
The intended remote is https://github.com/vanderlvoff/pravdareplikanta.git.
Source pushes and public site deployment are separate operations.

## Weather and current preview

The sample issue includes saved Ichikawa weather for 2026-10-29. Build and preview
without network:

```sh
rp build --issue 2026-10-29 --output previews/weather-review
rp preview --output previews/weather-review
```

An already-generated preview is available at `previews/weather-3`. Stop an older
server with Ctrl-C, then run `rp preview --output previews/weather-3` and open
http://127.0.0.1:8000/ru/ (also `/en/` and `/ja/`). Old snapshots remain unchanged.
Run from the repository root so `assets/` is available for integrity validation.

To acquire a new saved forecast, use the separate `rp weather` command described
in [docs/WEATHER.md](docs/WEATHER.md). Builds never refresh weather automatically.

## Browser review

Optional browser verification checks actual rendered quotation glyphs through
Chromium's font inspection, image loading, and mobile overflow:

```sh
python -m pip install -e '.[visual]'
python -m playwright install chromium
python scripts/check_header.py previews/weather-3 --language ru
```

Repeat with `--language en` or `--language ja`. For an existing Google Chrome
installation use `--channel chrome`. It records the actual browser version in
`browser-review-<language>.json` and saves `desktop-<language>.png` and
`mobile-<language>.png`. This diagnostic does not certify print reproducibility.

The Japanese motto uses bundled Zen Kurenaido Regular (SIL OFL 1.1). RU/EN mottos
use bundled Caveat-Regular. Actual font usage is checked in Chromium and PDF.

## Optional API editorial drafting

By owner request, `rp draft` can research primary sources and prepare RU/EN/JA
through OpenAI Responses API. It writes a separate generated issue with approved status, never publishing
or overwriting the canonical issue. See [docs/API_EDITORIAL.md](docs/API_EDITORIAL.md)
for secure key setup, model selection, dry-run and local build commands.
Normal newspaper generation remains offline and needs no API credentials.

## Editorial draft: 2026-10-30

The next issue contains RU/EN/JA analysis of Worken, learned demonstration timing
and RoboJev, based on primary publications dated October 23–29. It includes saved
Ichikawa weather for October 30 and remains a draft for editorial review.

```sh
rp preview --output previews/issue-2026-10-30-2
```

Open `/ru/`, `/en/` or `/ja/` and follow the PDF edition link. Older snapshots retain their original page counts; raster previews are under each language's issue directory.
See [source/review notes](docs/issues/2026-10-30.md) and the
[monthly API budget estimate](docs/API_BUDGET.md). This issue was prepared in the
current session without calling the paid OpenAI API.

## Import prepared daily JSON

Use `rp import` for the owner's `data/latest/{ru,en,ja}.json` feeds (`jp.json` is
also accepted for Japanese). See [docs/DAILY_IMPORT.md](docs/DAILY_IMPORT.md) for
commands, validation and section/page mapping. All incoming files stay unchanged.
The illustrated GitHub v1.3 issue (2026-10-31, revision 2) and October 30 history
have a local web and PDF archive preview:

```sh
rp preview --output previews/archive-2026-10-31-8
```
