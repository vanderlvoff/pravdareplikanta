# Local automatically paginated A4 proof

Install on macOS Intel or Apple Silicon in the activated Python 3.12+ environment:

```sh
python -m pip install -e '.[dev,pdf]'
python -m playwright install chromium --only-shell
rp build --issue 2026-10-30 --content-dir content/imported-v1.2-review --pdf --output previews/print-review
rp verify --issue 2026-10-30 --output previews/print-review
rp preview --output previews/print-review
```

Chromium downloads once; subsequent builds are offline. No Node, Docker or cloud
account is required. Ordinary web builds work without PDF dependencies.

## Pagination

Owner decision on 2026-10-30 supersedes the earlier three-page rule. Each language
gets as many A4 pages as needed. Text fills the left column, then the right column,
then the next page. The final page balances its two columns and may have unused space below them. Articles follow
section order: news, then analysis. Legacy `print_page` hints are accepted but ignored.

The first page keeps the supplied masthead, portrait/medals, weather and quote.
Later pages have a compact masthead. Article text stays at 10pt and headlines at
16pt. Columns, margins and artwork are never scaled to squeeze in more text.
Margins remain provisional 10mm pending a full-page approved reference.

Pinned Chromium measures font-loaded content before printing. Long plain-text
paragraphs can continue in another column, splitting at word boundaries where
available and Unicode character boundaries for Japanese. Headings reserve space
for the start of the following text. Source links and list items remain independent
blocks. An indivisible block taller than an empty column fails with a report.

The generator checks page/column bounds and adjacent text blocks for clipping and
intersection. It also records text fragments and verifies their PDF extraction,
plus completeness against the original article text. A machine check cannot
certify perfect visual harmony; inspect the raster previews for every language.

## Artifacts and verification

- `<lang>/issues/<date>/edition.pdf`: variable-length A4 portrait edition.
- `page-1.png` through `page-N.png`: every PDF page, rasterized for visual review.
- `pagination.json`: measured page count, article fragments and column fill ratios.
- `<lang>/print/`: persisted paginated HTML; PDF remains the print proof.
- `source.json`: exact editorial input, including weather.
- `verification.json`: geometry, resources, fonts and PDF checks.
- `artifacts.json`: checksums validated by `rp verify`.

Do not modify successful snapshots or add diagnostic files inside them. Build into
a fresh directory each time. Failed builds write `<output-name>.failed.json` and do
not replace a previous snapshot. Publishing remains a separate unimplemented step.

Pinned tools: Playwright 1.56.0, Chromium 141.0.7390.37 (build 1194), PyMuPDF 1.26.5.
External browser requests are blocked. Local assets are checksummed, and PDF time
metadata is removed for deterministic repeated builds in the same environment.
Verification also checks A4 dimensions, embedded fonts, RU/EN Caveat and Japanese Zen Kurenaido motto usage, missing
text/glyph heuristics and snapshot integrity. Page counts may differ by language.

Article fonts remain provisional system fonts by owner instruction. Motto fonts
are bundled: Caveat for RU/EN and Zen Kurenaido for JA. Full-page golden references are still absent: visual approval
is pending and cross-machine typography is not yet fully reproducible.

```sh
pytest
RP_TEST_PDF=1 pytest tests/test_pdf.py
ruff check .
ruff format --check .
```

Integration checks cover all three languages, repeated PDF byte equality, and a
long article continuing beyond three pages with full text preserved.

## Editorial illustrations

Image dimensions are read before layout and included as HTML width/height to
reserve geometry. Figures keep their aspect ratio, are limited to 65mm image
height and continue as indivisible units with their captions. The renderer waits
for cloned figure images to decode, checks figure bounds/adjacent blocks, and
records image placement by article/page. Verification compares placements and
caption extraction with source JSON. `RP_TEST_PDF=1 pytest tests/test_illustrations.py`
exercises all languages using clearly marked non-final fixture artwork.
