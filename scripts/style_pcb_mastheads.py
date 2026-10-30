"""Draw PCB traces inside only Pravda's original vector letter contours.

Run: python scripts/style_pcb_mastheads.py. Uses Python's standard library only.
Original SVGs and the earlier cyber-stencil study are never overwritten.
"""

import copy
import hashlib
import json
import random
import re
from bisect import bisect_right
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)


def add(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    return ET.SubElement(parent, f"{{{SVG}}}{tag}", attrs)


def routed_paths(
    paths: list[ET.Element], top: int, bottom: int, seed: int, *, pe_only: bool = False
) -> list[list[tuple[float, float]]]:
    """Route noncrossing nets through the actual letter interiors on a 14/3px grid with a clear contour margin."""
    edges = []
    for path in paths:
        tokens = re.findall(r"[MLZ]|-?\d+(?:\.\d+)?", path.attrib["d"])
        first = previous = None
        index = 0
        while index < len(tokens):
            command = tokens[index]
            index += 1
            if command == "Z":
                if previous and first:
                    edges.append((previous, first))
                continue
            point = (float(tokens[index]), float(tokens[index + 1]))
            index += 2
            if command == "M":
                first = point
            elif previous is not None:
                edges.append((previous, point))
            previous = point

    def crossings(y: float) -> list[float]:
        return sorted(
            x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            for (x1, y1), (x2, y2) in edges
            if (y1 > y) != (y2 > y)
        )

    pitch = 14 / 3
    clearance = 7.5
    allowed = set()
    for row in range(int((bottom - top - 2 * clearance) / pitch) + 1):
        y = top + clearance + row * pitch
        scans = [crossings(y + offset) for offset in (-clearance, 0, clearance)]
        for col in range(int((1985 - 64) / pitch) + 1):
            x = 64 + col * pitch
            if pe_only and x >= 388:
                continue
            if all(
                bisect_right(scan, x - clearance) % 2 and bisect_right(scan, x + clearance) % 2
                for scan in scans
            ):
                allowed.add((col, row))
    directions = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
    remaining = set(allowed)
    used_midpoints = set()
    rng = random.Random(seed)
    routes = []

    def choices(point: tuple[int, int]) -> list[tuple[int, tuple[int, int], tuple[int, int]]]:
        x, y = point
        options = []
        for direction, (dx, dy) in enumerate(directions):
            target = (x + dx, y + dy)
            middle = (2 * x + dx, 2 * y + dy)
            if target not in remaining or middle in used_midpoints:
                continue
            if dx and dy and ((x + dx, y) not in allowed or (x, y + dy) not in allowed):
                continue
            options.append((direction, target, middle))
        return options

    while remaining:
        candidates = rng.sample(sorted(remaining), min(24, len(remaining)))
        start = min(candidates, key=lambda point: len(choices(point)))
        route = [start]
        remaining.remove(start)
        previous_direction = None
        is_russian_pe = seed == 712 and 64 + start[0] * pitch < 388
        limit = rng.randint(12, 28) if is_russian_pe else rng.randint(16, 46)
        for _ in range(limit):
            options = choices(route[-1])
            if not options:
                break
            scored = []
            for direction, target, middle in options:
                turn = (
                    0
                    if previous_direction is None
                    else min(
                        (direction - previous_direction) % 8, (previous_direction - direction) % 8
                    )
                )
                if turn > 2:
                    continue
                score = rng.random() * 2.2 + (2.4 if turn == 0 else 0.8 if turn == 1 else 0)
                if is_russian_pe:
                    # Shorter fan-outs follow stems/crossbar instead of wrapping
                    # the whole Pe into nested rectangular frames.
                    horizontal = top + clearance + target[1] * pitch < 135
                    preferred = (0, 4) if horizontal else (2, 6)
                    score = rng.random() * 2.6 + (1.4 if turn == 0 else 1.3 if turn == 1 else 0.7)
                    score += 0.25 if direction in preferred else 0
                scored.append((score, direction, target, middle))
            if not scored:
                break
            _, previous_direction, target, middle = max(scored)
            used_midpoints.add(middle)
            remaining.remove(target)
            route.append(target)
        if len(route) >= 2:
            # Remove collinear vertices while retaining the routed bends.
            points = [route[0]]
            for index in range(1, len(route) - 1):
                a, b, c = route[index - 1 : index + 2]
                if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                    points.append(b)
            points.append(route[-1])
            routes.append([(64 + x * pitch, top + clearance + y * pitch) for x, y in points])
    return routes


def variant(language: str) -> Path:
    original = ET.parse(ASSETS / f"masthead/masthead_{language}.svg").getroot()
    root = ET.Element(original.tag, dict(original.attrib))
    title = original.find(f"{{{SVG}}}title")
    if title is not None:
        root.append(copy.deepcopy(title))
    add(root, "desc").text = (
        "Original silhouettes with PCB traces confined to Pravda only. "
        "The other word is unchanged; there are no displaced letters or exterior marks."
    )
    definitions = add(root, "defs")
    paths = [child for child in original if child.tag == f"{{{SVG}}}path"]
    if not paths:
        raise ValueError("Expected original outlined lettering")
    letters = add(definitions, "g", id="letterforms")
    clip = add(definitions, "clipPath", id="letter-interiors", clipPathUnits="userSpaceOnUse")
    for path in paths:
        letters.append(copy.deepcopy(path))
        outline = copy.deepcopy(path)
        outline.set("clip-rule", "evenodd")
        clip.append(outline)
    # The Japanese title reverses the words: Replicant above, Pravda below.
    top, bottom = (375, 652) if language == "ja" else (52, 406)
    word = add(definitions, "clipPath", id="pravda", clipPathUnits="userSpaceOnUse")
    add(word, "rect", x="0", y=str(top), width="2048", height=str(bottom - top))
    add(root, "use", href="#letterforms")
    selected = add(root, "g", **{"clip-path": "url(#pravda)"})
    interior = add(selected, "g", **{"clip-path": "url(#letter-interiors)"})
    # Remove every original solid fill in the styled word before drawing nets.
    # Clipping keeps the second word and the original exterior silhouette intact.
    paper = add(interior, "g")
    for path in paths:
        white = copy.deepcopy(path)
        white.set("fill", "white")
        paper.append(white)
    tracks = add(
        interior,
        "g",
        fill="none",
        stroke="black",
        **{
            "stroke-width": "1.7",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        },
    )
    routes = routed_paths(paths, top, bottom, {"ru": 712, "en": 913, "ja": 1217}[language])
    if language == "ru":
        # Refine Pe independently: all other letters keep their prior routes.
        routes = [route for route in routes if max(x for x, _ in route) >= 388]
        routes.extend(routed_paths(paths, top, bottom, 1712, pe_only=True))
    for route in routes:
        data = "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in route)
        add(tracks, "path", d=data)
        for x, y in (route[0], route[-1]):
            add(interior, "circle", cx=str(x), cy=str(y), r="1.9", fill="black")
    # Clear an uninterrupted white moat before drawing the thin black contour.
    # Its 7px inward extent leaves 5.5px of visible white beyond the outline.
    moat = add(interior, "g")
    for path in paths:
        edge = copy.deepcopy(path)
        edge.attrib.update(
            {"fill": "none", "stroke": "white", "stroke-width": "14", "stroke-linejoin": "round"}
        )
        moat.append(edge)
    # Thin black contours are clipped inward, with no remaining solid-fill islands.
    guard = add(interior, "g")
    for path in paths:
        boundary = copy.deepcopy(path)
        boundary.attrib.update(
            {"fill": "none", "stroke": "black", "stroke-width": "3", "stroke-linejoin": "round"}
        )
        guard.append(boundary)
    destination = ASSETS / f"masthead/pcb/masthead_{language}.svg"
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination


def main() -> None:
    generated = [variant(language) for language in ("ru", "en", "ja")]
    path = ASSETS / "MANIFEST.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    entries = [entry for entry in entries if not entry["path"].startswith("masthead/pcb/")]
    entries.extend(
        {"path": str(p.relative_to(ASSETS)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in generated
    )
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
