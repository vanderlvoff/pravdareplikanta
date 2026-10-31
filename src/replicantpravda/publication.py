"""Local reader-only release packaging; no upload, credentials or network calls."""

import json
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from .archive import archive_metadata
from .render import load_issue
from .verification import artifact_hashes, verify_site_links, verify_snapshot
from .telegram import make_announcement

MAX_ASSET_BYTES = 25 * 1024 * 1024


def reader_file(relative: str) -> bool:
    if relative in {"index.html", "style.css", "robots.txt", "sitemap.xml"}:
        return True
    if relative.startswith("assets/"):
        return Path(relative).suffix in {
            ".svg",
            ".png",
            ".jpeg",
            ".ttf",
            ".css",
        } or relative.endswith("/OFL.txt")
    if re.fullmatch(r"data/images/\d{4}-\d{2}-\d{2}/[a-z0-9-]+\.webp", relative):
        return True
    return bool(
        re.fullmatch(
            r"(?:ru|en|ja)/(?:(?:business|enthusiast|children)/)?(?:index\.html|rss\.xml|archive/index\.html|about/index\.html|"
            r"articles/[a-z0-9-]+/index\.html|issues/\d{4}-\d{2}-\d{2}/"
            r"(?:index\.html|edition\.pdf|articles/[a-z0-9-]+/index\.html))",
            relative,
        )
    )


def prepare_release(snapshot: Path, output: Path) -> dict:
    snapshot = snapshot.resolve()
    output = output.absolute()
    sidecar = output.with_name(output.name + ".release.json")
    if output.exists() or sidecar.exists():
        raise ValueError("Release output/report exists; choose a new path")
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError("Release output must be separate from the source snapshot")
    source = load_issue(snapshot / "source.json")
    verification = json.loads((snapshot / "verification.json").read_text(encoding="utf-8"))
    if verification.get("preview_only") is not False:
        raise ValueError("Use rp build --publication first; preview snapshots cannot be exported")
    archive = json.loads((snapshot / "archive.json").read_text(encoding="utf-8"))
    if not archive.get("pdf"):
        raise ValueError("Release requires verified PDFs; rebuild with --publication --pdf")
    issues = [
        load_issue(snapshot / "sources" / f"{date.fromisoformat(entry['issue_id'])}.json")
        for entry in archive["issues"]
    ]
    if any(issue.status not in {"approved", "published"} for issue in issues):
        raise ValueError("Release contains an unapproved issue")
    report = verify_snapshot(snapshot, str(source.issue_id))
    if not report["passed"]:
        raise ValueError("Publication snapshot verification failed")
    registry = snapshot / "reader-editions.json"
    if registry.exists():
        issues = [
            load_issue(snapshot / path)
            for paths in json.loads(registry.read_text())["editions"].values()
            for path in paths
        ]
    if any(entry.status not in {"approved", "published"} for entry in issues):
        raise ValueError("Release contains an unapproved issue")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".rp-release-") as directory:
        staging = Path(directory) / "public"
        staging.mkdir()
        for path in sorted(snapshot.rglob("*")):
            relative = path.relative_to(snapshot).as_posix()
            if not path.is_file() or not reader_file(relative):
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(snapshot):
                raise ValueError(f"Unsafe release file: {relative}")
            if path.stat().st_size > MAX_ASSET_BYTES:
                raise ValueError(f"Asset exceeds Cloudflare's 25 MiB limit: {relative}")
            if path.suffix == ".html" and 'name="robots" content="noindex' in path.read_text(
                encoding="utf-8"
            ):
                raise ValueError(f"Preview HTML cannot be released: {relative}")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        (staging / "404.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="robots" content="noindex"><title>404</title>'
            '<h1>404</h1><p><a href="/ru/">На главную</a> · '
            '<a href="/en/">Home</a> · <a href="/ja/">ホーム</a></p></html>\n',
            encoding="utf-8",
        )
        headers = "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        for edition in sorted({entry.edition for entry in issues}):
            for lang in ("ru", "en", "ja"):
                scope = lang if edition == "engineer" else f"{lang}/{edition}"
                headers += (
                    f"\n/{scope}/rss.xml\n  Content-Type: application/rss+xml; charset=utf-8\n"
                )
        headers += (
            "\nhttps://:worker.:account.workers.dev/*\n  X-Robots-Tag: noindex\n"
            "\nhttps://:version.:worker.:account.workers.dev/*\n  X-Robots-Tag: noindex\n"
        )
        (staging / "_headers").write_text(headers, encoding="utf-8")
        (staging / "announcement.json").write_text(
            json.dumps(
                make_announcement(
                    source, json.loads((snapshot / "site.json").read_text())["site_url"]
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        link_errors = verify_site_links(staging)
        if link_errors:
            raise ValueError("Release has missing reader links: " + "; ".join(link_errors[:5]))
        release = {
            "site_url": json.loads((snapshot / "site.json").read_text())["site_url"],
            "issues": [archive_metadata(issue) | {"edition": issue.edition} for issue in issues],
            "upload_review_required": True,
            "files": artifact_hashes(staging),
        }
        if len(release["files"]) > 20000:
            raise ValueError("Release exceeds 20,000 static assets")
        shutil.move(str(staging), str(output))
        sidecar.write_text(
            json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {"output": str(output), "files": len(release["files"]), "uploaded": False}
