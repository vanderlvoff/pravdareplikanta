# Local three-page print proof

Install on macOS Intel or Apple Silicon in the activated Python 3.12+ environment:

```sh
python -m pip install -e '.[dev,pdf]'
python -m playwright install chromium --only-shell
rp build --issue 2026-10-29 --pdf --output previews/print-review
rp verify --issue 2026-10-29 --output previews/print-review
rp preview --output previews/print-review
```

The first installation downloads Chromium. Subsequent builds are offline. Node,
Docker and a cloud account are not required. `--pdf` is opt-in; ordinary web builds
still work without the PDF dependencies. Install errors are never worked around by
silently selecting a system browser.

Open `/ru/`, `/en/` or `/ja/` on the preview server and follow the PDF link. Files:

- `<lang>/issues/2026-10-29/edition.pdf`: three A4 portrait pages.
- `<lang>/issues/2026-10-29/page-1.png` through `page-3.png`: raster previews.
- `<lang>/print/`: generated print HTML (PDF is the authoritative print proof).
- `verification.json`: geometry, resource, font and PDF checks, plus limitations.
- `source.json`: exact issue data used in this build, including saved weather.
- `artifacts.json`: SHA-256 inventory checked by `rp verify`.

Do not modify a successful snapshot or add diagnostic files inside it: verification
rejects any changed inventory. Use a new output directory for each revision.
Existing output is never overwritten. No publication command is provided.

## Editorial pagination

Each article has `print_page: 1`, `2` or `3` (default 1). The screen routes ignore this
field. Print articles on each page flow through two fixed-width columns at 10pt;
headlines use a fixed 16pt size. The masthead, weather and quotation appear on page
one; pages two and three have a compact running masthead. Layout constants use mm
and pt. Margins are provisional 10mm until a full-page approved reference exists.

The sample contains three short fictional editorial exercises, one per page, with
explicit placeholder sources. It intentionally leaves ample whitespace; it is not a
finished news issue or a density reference. A real editorial dataset can contain
multiple articles on each page.

The renderer measures page regions and column overflow before printing. It never
reduces all text to make it fit. On overflow it rejects the snapshot and writes
`<output-name>.failed.json` next to the requested output directory. The report names
the language, page and affected article IDs. Shorten or move articles in JSON and
rebuild into a fresh directory. Previous successful snapshots remain untouched.

## Renderer and verification

Pinned tools: Playwright 1.56.0, Chromium 141.0.7390.37 (build 1194), PyMuPDF 1.26.5.
The renderer requires the expected Playwright/Chromium versions and blocks external
browser resource requests. Images and Caveat bytes come from the checked asset
manifest. Chromium's generation timestamps are removed from PDFs; repeated builds
are byte-identical in the tested local environment.

Checks cover exactly three pages per language, A4 geometry (1pt renderer rounding
tolerance), text within page bounds, expected article text, issue date/title,
replacement/null characters, embedded font resources and RU/EN quotation glyphs
actually using Caveat-Regular. All nine pages are rasterized. `rp verify` checks
artifact hashes and repeats PDF checks without launching a browser or using the
network. It requires a snapshot originally built with `--pdf`.

Glyph/text checks are heuristics. A successful machine check cannot certify visual
fidelity, every font glyph shape, or absence of every possible overlap. Inspect the
nine PNG pages manually. Full-page golden comparisons remain pending.

## Temporary font exception

By owner instruction, article text/headlines and Japanese quotations currently use
system fonts. Caveat-Regular is bundled and embedded for RU/EN quotations. The print
report records actual quotation fonts and embedded PDF font resources. Japanese
system glyphs may be embedded as Type3 outlines by Chromium.

This is a NON-FINAL local proof. Cross-machine typography is not reproducible until
body and Japanese quotation fonts are approved, bundled and checksummed. No supplied
artwork is redrawn, cropped or distorted.

## Tests

```sh
pytest
RP_TEST_PDF=1 pytest tests/test_pdf.py
ruff check .
ruff format --check .
```

The integration test renders all languages, checks nine page previews, compares
repeated PDFs byte for byte, then intentionally overflows an article and requires a
failed build plus an editorial report.
