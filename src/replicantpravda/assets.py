"""Verify owner-supplied local assets before copying bytes unchanged."""

import hashlib
import json
import shutil
from pathlib import Path


def copy_assets(source: Path, destination: Path) -> None:
    entries = json.loads((source / "MANIFEST.json").read_text(encoding="utf-8"))
    indexed = {entry["path"]: entry["sha256"] for entry in entries}
    required = {"portrait/batty.png", "fonts/Caveat/static/Caveat-Regular.ttf"}
    for lang in ("ru", "en", "ja"):
        required.add(f"masthead/masthead_{lang}.svg")
        for name, extension in (("orion", "jpeg"), ("jupiter", "jpeg"), ("tannhauser", "png")):
            required.add(f"medals/{lang}/{name}_{lang}.{extension}")
    if not required <= indexed.keys():
        raise ValueError("Manifest lacks required header assets")
    for relative, expected in indexed.items():
        path = (source / relative).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError(f"Missing or unsafe asset: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Asset checksum mismatch: {relative}")
    for relative in sorted(required | {"fonts/Caveat/OFL.txt"}):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
