# Supplied graphics bundle

- `masthead/pcb/masthead_{ru,en,ja}.svg`: current PCB variants, styling Pravda only.
- `masthead/cyber/masthead_{ru,en,ja}.svg`: previous cyber-stencil study, retained.
- `masthead/masthead_{ru,en,ja}.svg`: original supplied outline mastheads, unchanged. See masthead/README.md for provenance.
- `masthead/preview_*.png`: supplied preview renders.
- `medals/{ru,en,ja}/`: nine original language-specific medals, unchanged.
- `portrait/ly.png`: current owner-supplied portrait, unchanged.
- `portrait/batty.png`: previous supplied portrait retained unchanged.
- `reference/`: two supplied header reference images; full-page golden PDFs are not present.
- `fonts/Caveat/static/Caveat-Regular.ttf`: quotation font; license in `fonts/Caveat/OFL.txt`.

MANIFEST.json records SHA-256 checksums of the supplied graphics, fonts and font
license/text files. Build checks the recorded files before copying required header
assets and the Caveat license into the local preview. Updating the manifest is a
reviewed source change, never an automatic build operation.

By owner instruction, article body and headline fonts remain provisional system
sans-serif. The supplied assets are not redrawn, cropped or stretched. The web
composition is provisional and does not certify a match to the reference.
The RU/EN/JA motto uses the owner-supplied wording updated on 2026-10-30. Weather data is not invented from a historical reference.

The Japanese motto uses bundled `fonts/ZenKurenaido/ZenKurenaido-Regular.ttf`;
license: `fonts/ZenKurenaido/OFL.txt` (SIL OFL 1.1). Source commit is pinned in
its README. RU/EN mottos use bundled Caveat-Regular.

## Experimental press medals (owner requested)

The header now uses `medals/press/*.png`: one-bit black/white derivatives with
contrast enhancement, sharpening and a deterministic ordered halftone. Supplied
files in `medals/{ru,en,ja}/` remain byte-for-byte unchanged. This is an experimental
print treatment for visual review, not a newly approved reference.

Reproduce from the repository root:

```sh
python -m pip install -e '.[artwork]'
python scripts/process_medals.py
```

Pillow is pinned to 12.0.0 and needed only when regenerating artwork. Ordinary
builds copy checked-in, checksummed derivatives without image-processing dependencies.
The script also writes `spacing.css`, which halves the gaps measured between the
original non-white horizontal bounds (threshold 225), keeping each medal's display
size and aspect ratio. Original canvas bounds are retained in the derivative.
Processing parameters are explicit in the script; regeneration updates only the
derivative entries in MANIFEST.json. Batty and the masthead are untouched.
