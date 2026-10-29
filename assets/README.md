# Supplied graphics bundle

- `masthead/masthead_{ru,en,ja}.svg`: supplied outline mastheads. See masthead/README.md for provenance.
- `masthead/preview_*.png`: supplied preview renders.
- `medals/{ru,en,ja}/`: nine original language-specific medals, unchanged.
- `portrait/batty.png`: supplied portrait, unchanged.
- `reference/`: two supplied header reference images; full-page golden PDFs are not present.
- `fonts/Caveat/static/Caveat-Regular.ttf`: quotation font; license in `fonts/Caveat/OFL.txt`.

MANIFEST.json records SHA-256 checksums of the supplied graphics, fonts and font
license/text files. Build checks the recorded files before copying required header
assets and the Caveat license into the local preview. Updating the manifest is a
reviewed source change, never an automatic build operation.

By owner instruction, article body and headline fonts remain provisional system
sans-serif. The supplied assets are not redrawn, cropped or stretched. The web
composition is provisional and does not certify a match to the reference.
The Russian quotation is transcribed from the supplied reference; The English quotation is included; the Japanese quotation uses owner-supplied wording. Weather data is not invented from a historical reference.

Japanese quotations temporarily use the system Japanese serif font: Caveat has no Japanese glyphs. RU/EN quotations use bundled Caveat-Regular.
