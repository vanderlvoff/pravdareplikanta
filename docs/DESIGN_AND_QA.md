# Print layout and visual quality gates

## Objective

A reproducible three-page A4 PDF edition in RU/EN/JA with the owner's approved Soviet *Pravda*-inspired masthead and medal block.

## Geometry

- A4 portrait: 210 × 297 mm. Explicit `@page { size: A4; margin: ... }` with margin dimensions derived from the approved PDF.
- Use physical units (mm or pt) for print header, medals, masthead, artwork positioning.
- Fix grid tracks and bounding boxes where appropriate. Flow article text in managed regions; prevent overflow.
- Screen layouts may be responsive and visually related, but not pixel-identical to the fixed A4 PDF.
- For newspaper typography, proof language-dependent hyphenation and Japanese break opportunities; do not force uniform line counts across languages.

## Assets

- Approved portrait of Roy Batty, final medals, masthead visual and font files must be supplied by user, copied to the repository, and checksummed.
- Do not substitute system fonts silently. Fail with a descriptive error for missing expected fonts.
- Caveat quotation font should be confirmed to contain required Cyrillic glyphs, embedded into PDFs, and tested with Russian text.
- Medal inscriptions use proper language variant. Align upper medal edges and preserve relative size, especially Hero of Tannhäuser.
- No extra labels under medals unless explicitly part of the approved reference.
- Preserve exact agreed portrait width/height/proportions and weather composition.

## Automated checks

1. Validate all required assets present and hashes match a manifest.
2. Render PDF with pinned Playwright browser, wait for fonts and images loaded.
3. Extract PDF metadata: page count exactly 3 per locale, expected page dimensions A4.
4. Check for overflow via DOM geometry before printing (element scroll bounding comparisons, regions beyond page boundaries).
5. Check text extraction includes mandatory masthead/date/issue number; PDF raster inspection for missing glyphs.
6. Rasterize all pages and compare against approved golden images when available, using appropriate image difference tolerance.
7. Produce human-readable `verification.json` and visual preview PNGs; block deploy on failures.

## Explicit regression cases

- Right edge of Cyrillic masthead must not be cropped.
- No white overlay rectangle over English title.
- Top borders of three medals must align; Hero of Tannhäuser must match the approved design.
- Portrait is not squashed and keeps the agreed stylized likeness.
- Weather box formatting clean and without an unwanted JMA footer line if the approved design excludes it.
- Generation instructions and debugging statements must not appear as newspaper content.

## Manual signoff

Even after automated checks pass, human must inspect all three languages and mark issue APPROVED. Reference-perfect compliance cannot be claimed until owner supplies golden PDFs/images.

## Current local implementation

See [PRINT.md](PRINT.md) for the implemented PDF workflow and measured limitations.
By owner instruction, article fonts and Japanese quotation fonts are temporarily
system fonts; they remain a reproducibility limitation until approved files arrive.
The 10mm print margins are provisional because full-page golden references are absent.
