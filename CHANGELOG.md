# Changelog

## Unreleased

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
