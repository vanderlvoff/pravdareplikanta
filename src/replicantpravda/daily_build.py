"""Prepare a complete daily release in an isolated checkout; never push."""

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .importer import FeedEdition, import_feed
from .models import Issue
from .publication import prepare_release
from .readers import READER_EDITIONS
from .render import build, load_issue
from .weather import LOCATIONS, fetch_forecast


def data_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((root / "data").rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in source data")
        if path.is_file() and "revisions" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def load_history(root: Path) -> dict[tuple[str, date], Issue]:
    history = {}
    for folder in (root / "content/technical", root / "content/editions"):
        for path in sorted(folder.rglob("*.json")) if folder.exists() else []:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", path.name):
                issue = load_issue(path)
                if issue.status not in {"approved", "published"}:
                    continue
                history[issue.edition, issue.issue_id] = issue
    return history


def prepare(root: Path, output: Path, *, force: bool = False, today: date | None = None) -> dict:
    today = today or datetime.now(ZoneInfo("Asia/Tokyo")).date()
    digest = data_digest(root)
    manifest_path = root / "public.release.json"
    old_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not force and old_manifest.get("source_data_sha256") == digest:
        return {"changed": False, "reason": "No new data"}
    feeds = {
        code: {
            lang: FeedEdition.model_validate_json(
                (root / "data/latest" / code / f"{lang}.json").read_text()
            )
            for lang in ("ru", "en", "ja")
        }
        for code in READER_EDITIONS
    }
    day = feeds["engineer"]["ru"].issue_date
    if day < today:
        return {"changed": False, "reason": "Waiting for today's data", "issue_id": str(day)}
    if day != today or any(
        f.issue_date != day for values in feeds.values() for f in values.values()
    ):
        raise ValueError("All twelve feeds must have today's Tokyo date")
    history = load_history(root)
    primary_history = sorted(
        (i for i in history.values() if i.edition == "engineer"), key=lambda i: i.issue_id
    )
    if not primary_history:
        raise ValueError("A numbered engineering template is required")
    template = primary_history[-1]
    if template.issue_id > day:
        raise ValueError("Refusing to move the published issue date backwards")
    same_day = history.get(("engineer", day))
    number = same_day.number if same_day else template.number + 1
    released_today = any(i["issue_id"] == str(day) for i in old_manifest.get("issues", []))
    revision = (same_day.revision + int(released_today)) if same_day else 1

    # On the first migration, normalize explicit historical audience folders using
    # known issue numbers/weather. Later runs preserve the published sources.
    for old in list(primary_history):
        if old.issue_id >= day:
            continue
        folder = root / "data/archive" / old.issue_id.strftime("%Y/%m/%d")
        for code in READER_EDITIONS:
            if (code, old.issue_id) in history and code != "engineer":
                continue
            if (root / "content/editions" / code / f"{old.issue_id}.json").exists():
                continue
            if (folder / code).is_dir():
                archived, _ = import_feed(
                    folder / code, old, number=old.number, revision=old.revision
                )
                history[code, old.issue_id] = archived

    saved_weather = {}
    for lang, location in (("ru", "ichikawa"), ("en", "breukelen"), ("ja", "smolensk")):
        existing = template.languages[lang].weather or (template.weather if lang == "ru" else None)
        saved_weather[lang] = (
            existing
            if existing and existing.forecast_date == day
            else fetch_forecast(day, location)
        )
        if saved_weather[lang].timezone != LOCATIONS[location][2]:
            raise ValueError("Incorrect weather location")
    template_data = template.model_dump()
    template_data.update(issue_id=day, publication_date=day, number=number, revision=revision)
    template_data["weather"] = saved_weather["ru"]
    for lang, weather in saved_weather.items():
        template_data["languages"][lang]["weather"] = weather
    template = Issue.model_validate(template_data)
    for code in READER_EDITIONS:
        issue, _ = import_feed(
            root / "data/latest" / code, template, number=number, revision=revision
        )
        if issue.edition != code or issue.issue_id != day:
            raise ValueError("Feed folder/date differs from edition")
        history[code, day] = issue
    issues = list(history.values())
    primary = history["engineer", day]
    snapshot = output / "snapshot"
    build(
        primary,
        snapshot,
        site_url="https://repravda.com",
        archive_issues=tuple(i for i in issues if i.edition == "engineer" and i.issue_id != day),
        reader_issues=tuple(i for i in issues if i.edition != "engineer"),
        pdf=True,
        publication=True,
    )
    release = output / "public"
    prepare_release(snapshot, release)
    release_manifest = release.with_name("public.release.json")
    metadata = json.loads(release_manifest.read_text())
    metadata["source_data_sha256"] = digest
    release_manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    for issue in issues:
        target = root / "content/editions" / issue.edition / f"{issue.issue_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(issue.model_dump_json(indent=2) + "\n")
    for weather in saved_weather.values():
        target = root / "content/weather" / f"{weather.location}-{day}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(weather.model_dump_json(indent=2) + "\n")
    return {"changed": True, "issue_id": str(day), "number": number, "revision": revision}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = prepare(Path.cwd(), args.output, force=args.force)
    (args.output / "result.json").write_text(json.dumps(result) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
