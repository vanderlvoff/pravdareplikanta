"""Copy explicitly referenced repository WebPs; never fetch remote article images."""

import hashlib
from pathlib import Path

from .models import Issue

MAX_BYTES = 20_000_000


def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("Illustration must be a WebP image")
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError("Truncated or inconsistent WebP illustration")
    offset = 12
    while offset + 8 <= len(data):
        kind = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        chunk = data[offset + 8 : offset + 8 + size]
        if len(chunk) != size:
            raise ValueError("Truncated WebP illustration")
        if kind == b"VP8X" and len(chunk) >= 10:
            if chunk[0] & 2:
                raise ValueError("Animated illustrations are not supported")
            return int.from_bytes(chunk[4:7], "little") + 1, int.from_bytes(
                chunk[7:10], "little"
            ) + 1
        if kind == b"VP8L" and len(chunk) >= 5 and chunk[0] == 47:
            bits = int.from_bytes(chunk[1:5], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8 " and len(chunk) >= 10 and chunk[3:6] == b"\x9d\x01\x2a":
            return int.from_bytes(chunk[6:8], "little") & 0x3FFF, int.from_bytes(
                chunk[8:10], "little"
            ) & 0x3FFF
        offset += 8 + size + (size % 2)
    raise ValueError("Missing WebP image dimensions")


def copy_illustrations(issue: Issue, source_root: Path, destination: Path) -> dict[str, dict]:
    images = {}
    root = source_root.resolve()
    for edition in issue.languages.values():
        for article in edition.articles:
            image = article.image
            if image is None or image.path in images:
                continue
            source = (root / image.path).resolve()
            if not source.is_relative_to(root / "data/images") or not source.is_file():
                raise ValueError(
                    f"Missing or unsafe local illustration: {image.path}; update repository data/images"
                )
            if source.stat().st_size > MAX_BYTES:
                raise ValueError(f"Illustration exceeds 20 MB: {image.path}")
            data = source.read_bytes()
            width, height = webp_dimensions(data)
            if not 0 < width <= 10000 or not 0 < height <= 10000 or width * height > 25_000_000:
                raise ValueError(f"Illustration dimensions exceed limits: {image.path}")
            target = destination / image.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            images[image.path] = {
                "width": width,
                "height": height,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    return images
