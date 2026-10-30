# Approved masthead — 2026-10-30

The owner approved the current RU/EN/JA PCB variants in `pcb/` with the final
Russian П refinement, as shown in `previews/latest-2026-10-30-25`.
`APPROVAL.json` records the exact SHA-256 hashes. Treat these SVGs as immutable
approved artwork; any further visual changes require a new owner request.
This approval covers the masthead artwork, not full-page layout or publication.
Previous studies below document the design history and are superseded by this approval.

# Mastheads — true vector SVG from approved transparent PNGs

- `masthead_ru.svg`, `masthead_en.svg`, `masthead_ja.svg`: three real vector SVGs made of path outlines; they do **not** embed bitmap PNGs or depend on fonts.
- **No redesign, retyping, recoloring or letter repositioning** was performed. All outlines are traced from the previously approved, normalized transparent PNG images.
- Each SVG has the same `viewBox="0 0 2048 704"`, transparent background, and nominal letter bounds `x=64..1984`, `y=52..652`.
- `preview_*.png` are reference renders of the SVGs for inspection; they are not used as SVG internals.
- Note: anti-aliased edge pixels may differ slightly because SVG renderers use their own antialiasing; the silhouettes match to the pixel level.

These are for placement in the header, with a single shared CSS/HTML box size for all three languages.

## Cyber-stencil variants — 2026-10-30

At the owner's request, `cyber/masthead_{ru,en,ja}.svg` provides a shared
black-and-white treatment: narrow stencil cuts, a displaced scan band on each
line, and registration corners. Original files above remain unchanged. The
variants reuse the supplied outlined letterforms; they are a styling study, not
a separately drawn alphabet. All three retain the original 2048 × 704 viewBox.

Regenerate with `python scripts/style_mastheads.py` (standard library only).
The script reads originals, writes only `cyber/` derivatives, and updates their
manifest entries. SVGs contain local paths, masks, clip paths and internal uses;
there are no font dependencies, embedded bitmaps or external resources.

The web masthead and continuation print headers now use these variants.
Side-by-side local proof: `previews/masthead-cyber-review/comparison.png`.
Final graphical approval remains with the owner.

## PCB variant — 2026-10-30

Current headers use `pcb/masthead_{ru,en,ja}.svg`, generated from the original
files above by `python scripts/style_pcb_mastheads.py`. Only Pravda receives white
PCB routes and annular pads: upper row in RU/EN, lower row プラウダ in Japanese.
The other word is unchanged. There is no glitch or exterior decoration.

Internal clipping and a clipped inner boundary stroke keep traces away from the
original exterior contours and counters. Everything remains vector: paths, circles
and clip paths, with no filters, font dependencies or embedded raster images.
Originals and the earlier cyber study remain available and unchanged.

Side-by-side proof: `previews/masthead-pcb-review/comparison.png`.

The current PCB revision uses denser four-track bundles, staggered meanders, via
banks and connector fan-outs. Dense proof: `previews/masthead-pcb-dense-review/comparison.png`.

The latest PCB revision replaces clustered bundles with constant-pitch routing,
staggered bends and dispersed vias for uniform coverage. Current proof:
`previews/masthead-pcb-even-review/comparison.png`.

## Shape-aware routing revision

The current PCB design uses actual original M/L/Z contours to find interior routing
space on a 14px grid. Individual nets take orthogonal and 45-degree turns, avoid
occupied vertices and crossing edge midpoints, and end in solid contact pads.
Fixed per-language seeds make regeneration deterministic. Routes are constructed
for each alphabet's silhouettes, with no tiled motif or copied reference paths.
The supplied reference informs the visual routing vocabulary only.

Current proof: `previews/masthead-pcb-routed-review/comparison.png`. Earlier
proofs and immutable issue snapshots retain the previous design iterations.

The current inverted version has white letter interiors, black PCB routes and
contacts, and thin black inward-clipped contours. Original solid fills are cleared
entirely within Pravda; there are no retained black fill islands. Short routes
are also drawn to fill narrow areas. Current proof:
`previews/masthead-pcb-inverse-review/comparison.png`.

Latest PCB scale: 7px routing pitch, 2.1px tracks and 2.4px terminal radii,
with 3px inward-clipped contour strokes. This halves the prior linear feature
size and doubles linear routing density. Fine proof:
`previews/masthead-pcb-fine-review/comparison.png`.

Current routing pitch is 14/3px, 1.5× denser linearly than the 7px revision.
Tracks are 1.7px with 1.9px terminal radii. A clipped 14px white edge stroke clears
a 7px interior band before the 3px black contour, preserving a visible white gap.
Russian П uses shorter routes with stem/crossbar direction preferences.
Current proof: `previews/masthead-pcb-refined-review/comparison.png`.

Russian П is now routed independently with the same turn/length rules as the other
letters. Other routes and EN/JA variants remain unchanged. Current proof:
`previews/masthead-pcb-pe-review/comparison.png`.
