# Changelog

## Unreleased

- Added daily feed v1.3 support for exactly two shared, localized editorial illustrations per edition.
- Added offline WebP copying, path/URL validation, source checksums, accessible figures and AI illustration labels in web and print.
- Integrated indivisible figures into automatic pagination, with image loading, placement and caption verification.

- Added the same small weather country label to the Russian edition: Итикава (Япония).

- Set the Japanese translated title and strapline on one line; added small country labels beside EN/JA weather cities without uppercase transformation.

- Removed web link underlines and added restrained teal hover/focus highlighting with keyboard focus indicators.
- Added translated newspaper names above EN/JA straplines, keeping approved SVGs unchanged.
- Added per-edition saved forecasts: EN Breukelen (Netherlands), JA Smolensk, RU Ichikawa, with local timezones and source footers.

- Bundled owner-selected Zen Kurenaido Regular with OFL license for the Japanese motto; added actual browser font and PDF embedding verification.

- Owner approved and froze the current RU/EN/JA PCB mastheads, including the final Russian П refinement; recorded exact hashes in assets/masthead/APPROVAL.json.

- Calmed Russian П with longer, straighter shape-aware routes consistent with the other letters, preserving all other letter routes and EN/JA SVGs.

- Increased PCB linear routing density by 1.5× (7px to 14/3px pitch), added a continuous white clearance band inside contours, and revised Russian П with shorter stem/crossbar fan-outs.

- Changed the top line from road to path (RU/EN), narrowed the motto to 84% and reduced its type size by one third on screen and in print.
- Halved PCB routing scale (14px to 7px pitch, with proportionally thinner tracks/pads) for twice the linear density.

- Inverted PCB Pravda lettering to black routes on white interiors with thin inward-clipped outlines; removed original solid fills and included short routes for coverage.

- Replaced repeating PCB texture with individually routed, noncrossing nets following each original letter interior, inspired by the owner reference without reproducing its paths.

- Equalized PCB lettering density with a constant routing pitch, staggered bends and evenly distributed vias, replacing clustered bundles.

- Densified the PCB lettering with four-track routing bundles, staggered meanders, via banks and connector pads while preserving original contours.

- Added PCB masthead variants based on original SVGs: only Pravda receives interior traces/pads; the other word and exterior letter contours remain original in RU/EN/JA.

- Added owner-requested RU/EN/JA cyber-stencil masthead studies with shared cuts, displaced scan bands and registration corners; original SVGs remain unchanged.

- Replaced the RU/EN/JA motto with owner-supplied wording and switched the header portrait to original ly.png; removed the obsolete Roy Batty attribution.

- Added two-column article listings and article body text on wide web screens; narrow screens retain a single reading column.

- Removed the three-page limit at owner request; A4 columns now fill sequentially and continue automatically with fixed type sizes.
- Added measured paragraph splitting, heading attachment, actual page numbering, per-article pagination maps, text-coverage and overlap checks. Final-page space is allowed.

- Imported GitHub v1.2 daily feeds with eight editorial body articles per language; retained time_window validation and added regression coverage against the archived v1.2 feed.
- Built a web-only preview; three-page PDF overflow is reported for editorial pagination.

- Daily news now renders title/body only; legacy editorial fields are optional and excluded from reader output. Newline-separated body paragraphs are preserved and missing body fails import.

- Added owner-requested high-contrast, one-bit press medal derivatives generated with Python; original artwork remains unchanged.
- Halved the visible horizontal medal gaps, accounting for whitespace inside each original image.

- Removed the extra screen-only divider above the morning forecast.
- Grouped web articles into localized News/Analysis sections and replaced repeated print category tags with section headings.
- Updated the top line to “Physical AI — дорога в прекрасное далёко.” with EN/JA translations.

- Added offline import of owner's RU/EN/JA daily feeds, including jp filename alias, source validation and provenance hashes.
- Preserved all news, technical/evidence notes, technology signal and glossary in screen/print output.
- Added issue-specific title and lead to the first printed page without changing the masthead.
- Kept category/headline/dek groups together across print columns.
- Added the imported 2026-10-30 revision 2 separately from the previous editorial draft.

- Added the 2026-10-30 RU/EN/JA editorial draft reviewing primary sources dated October 23–29, with a fresh saved Ichikawa forecast.
- Balanced print columns without changing the fixed article font sizes.
- Documented an assumption-based monthly API budget and issue-specific source/review notes.

- Improved API failure messages with allowlisted provider error codes and Retry-After, without logging server error messages or credentials.

- Added owner-requested optional OpenAI API research and structured multilingual draft acquisition.
- Added explicit model/token/tool limits, dry-run, source URL checks and draft-only audit files.
- Kept API keys in environment variables and API calls outside normal offline generation.

- Added opt-in three-page A4 PDFs for RU/EN/JA using pinned Chromium and shared header assets.
- Added explicit editorial page assignment, two-column print layout and PDF links.
- Added raster previews, overflow reports, font/text/page checks and snapshot verification.
- Added short fictional articles for pages two and three of the sample issue.
- Kept article and Japanese quotation fonts provisional by owner instruction.

- Placed conditions and wind to the right of each weather time/temperature on desktop; retained readable stacked details on narrow screens.

- Added localized Ichikawa weather at 09:00/12:00/18:00 JST, daily range, precipitation and wind.
- Added explicit forecast acquisition, saved JSON, offline rendering and source/time attribution.
- Added a real weather snapshot to the sample issue and synthetic offline test fixtures.
- Expanded browser checks to all languages, failed image requests and mobile overflow.
- Increased local preview server connection backlog for simultaneous image/font requests.

- Replaced the Japanese quotation with owner-supplied wording and removed the draft translation label.

- Added English and draft Japanese masthead quotations and localized credits.
- Kept Caveat for RU/EN; explicitly used a provisional Japanese serif stack because Caveat lacks Japanese glyphs.

- Removed the remaining CSS gap between medals and enlarged Orion by another 5%.

- Tightened medal spacing and increased Orion by approximately 5%, preserving proportions.

- Ordered medals Jupiter → Tannhäuser → Orion across editions.
- Reduced portrait/medals block dimensions to 80%, preserving image proportions.

- Rebuilt screen header grid with portrait/medals, masthead/strapline and weather column.
- Made the root page show the Russian edition and versioned CSS URLs to avoid stale styling.
- Verified actual Caveat-Regular glyph rendering in Chrome; added repeatable browser proof script.
- Weather column explicitly marks missing forecast data; no reference forecast is reused as current.

- Added supplied multilingual masthead SVGs, original medals and portrait to local web previews.
- Added bundled Caveat-Regular for quotations and the Russian reference quotation.
- Added asset integrity checks; article fonts remain provisional by owner instruction.

## 0.1.0 — 2026-10-29

- Added strict multilingual JSON validation and deterministic offline website previews.
- Added generic NON-FINAL screen templates, localized routes and article links.
- Added loopback-only preview command; publication and print output remain unavailable.
