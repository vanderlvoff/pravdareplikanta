# Mastheads — true vector SVG from approved transparent PNGs

- `masthead_ru.svg`, `masthead_en.svg`, `masthead_ja.svg`: three real vector SVGs made of path outlines; they do **not** embed bitmap PNGs or depend on fonts.
- **No redesign, retyping, recoloring or letter repositioning** was performed. All outlines are traced from the previously approved, normalized transparent PNG images.
- Each SVG has the same `viewBox="0 0 2048 704"`, transparent background, and nominal letter bounds `x=64..1984`, `y=52..652`.
- `preview_*.png` are reference renders of the SVGs for inspection; they are not used as SVG internals.
- Note: anti-aliased edge pixels may differ slightly because SVG renderers use their own antialiasing; the silhouettes match to the pixel level.

These are for placement in the header, with a single shared CSS/HTML box size for all three languages.
