"""Create reversible, shared cyber-stencil SVG variants of supplied mastheads.

Run from any directory: python scripts/style_mastheads.py
Original SVGs are read only. No rasterization, font substitution or network access.
"""

import copy
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def element(name: str, attributes: dict[str, str], parent: ET.Element) -> ET.Element:
    return ET.SubElement(parent, f"{{{SVG}}}{name}", attributes)


def create_variant(source: Path, destination: Path) -> None:
    original = ET.parse(source).getroot()
    root = ET.Element(original.tag, dict(original.attrib))
    title = original.find(f"{{{SVG}}}title")
    if title is not None:
        root.append(copy.deepcopy(title))
    description = element("desc", {}, root)
    description.text = (
        "Cyber-stencil study: supplied letterforms with shared stencil cuts, "
        "a displaced scan band on each line and registration corners."
    )
    definitions = element("defs", {}, root)
    letterforms = element("g", {"id": "letterforms"}, definitions)
    for child in original:
        if child.tag == f"{{{SVG}}}path":
            letterforms.append(copy.deepcopy(child))
    if not len(letterforms):
        raise ValueError(f"No supplied vector letterforms in {source}")
    mask = element(
        "mask",
        {
            "id": "stencil",
            "maskUnits": "userSpaceOnUse",
            "x": "0",
            "y": "0",
            "width": "2048",
            "height": "704",
            "style": "mask-type:luminance",
        },
        definitions,
    )
    element("rect", {"width": "2048", "height": "704", "fill": "white"}, mask)
    # Shared narrow cuts preserve the individual alphabets' original readability.
    for x, y, height in (
        (365, 52, 354),
        (1040, 52, 354),
        (1680, 52, 354),
        (520, 430, 222),
        (1130, 430, 222),
        (1700, 430, 222),
    ):
        element(
            "rect",
            {"x": str(x), "y": str(y), "width": "9", "height": str(height), "fill": "black"},
            mask,
        )
    for y, height in ((210, 20), (526, 18)):
        element(
            "rect", {"y": str(y), "width": "2048", "height": str(height), "fill": "black"}, mask
        )
    element("use", {"href": "#letterforms", "mask": "url(#stencil)"}, root)
    for name, y, height, shift in (("scan-top", 214, 12, 12), ("scan-bottom", 530, 10, 9)):
        clip = element("clipPath", {"id": name, "clipPathUnits": "userSpaceOnUse"}, definitions)
        element("rect", {"y": str(y), "width": "2048", "height": str(height)}, clip)
        element(
            "use",
            {
                "href": "#letterforms",
                "clip-path": f"url(#{name})",
                "transform": f"translate({shift} 0)",
            },
            root,
        )
    corners = element("g", {"fill": "none", "stroke": "#000", "stroke-width": "4"}, root)
    element(
        "path", {"d": "M42 52H22V78 M2006 52H2026V78 M42 652H22V626 M2006 652H2026V626"}, corners
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def main() -> None:
    generated = []
    for language in ("ru", "en", "ja"):
        relative = f"masthead/cyber/masthead_{language}.svg"
        path = ASSETS / relative
        create_variant(ASSETS / f"masthead/masthead_{language}.svg", path)
        generated.append(
            {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    path = ASSETS / "MANIFEST.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    entries = [entry for entry in entries if not entry["path"].startswith("masthead/cyber/")]
    path.write_text(json.dumps(entries + generated, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
