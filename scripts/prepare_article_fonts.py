"""Freeze the bundled Noto Serif JP variable source at 400/700 for Chromium PDF."""

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

FONTTOOLS_VERSION = "4.60.1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=Path("assets"))
    parser.add_argument("--update-manifest", action="store_true")
    args = parser.parse_args()
    if version("fonttools") != FONTTOOLS_VERSION:
        raise ValueError(f"Regeneration requires fonttools=={FONTTOOLS_VERSION}")
    manifest_path = args.assets / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    indexed = {entry["path"]: entry["sha256"] for entry in manifest}
    relative_source = "fonts/NotoSerifJP/NotoSerifJP-Variable.ttf"
    source = args.assets / relative_source
    if hashlib.sha256(source.read_bytes()).hexdigest() != indexed[relative_source]:
        raise ValueError("Bundled Noto source differs from its pinned checksum")
    generated = []
    for label, weight in (("Regular", 400), ("Bold", 700)):
        with TTFont(source, recalcTimestamp=False) as variable:
            font = instantiateVariableFont(variable, {"wght": weight}, updateFontNames=True)
            font.recalcTimestamp = False
            if "fvar" in font or font["name"].getDebugName(6) != f"NotoSerifJP-{label}":
                raise ValueError("Unexpected static font instance")
            target = source.with_name(f"NotoSerifJP-{label}.ttf")
            font.save(target)
            font.close()
        relative = str(target.relative_to(args.assets))
        generated.append(
            {"path": relative, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        )
        print(f"Prepared {relative} (wght={weight})", flush=True)
    if args.update_manifest:
        replaced = {entry["path"] for entry in generated}
        manifest = [entry for entry in manifest if entry["path"] not in replaced] + generated
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
