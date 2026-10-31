"""GitHub runner entrypoint. No bot request in prepare or dry-run modes."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request
from zoneinfo import ZoneInfo

from replicantpravda.telegram import (
    PRODUCTION_ORIGIN,
    check_bot,
    request_bytes,
    send_announcement,
    validate_announcement,
    validate_bot_token,
)

REPOSITORY = "vanderlvoff/pravdareplikanta"
CHECK_NAME = "Workers Builds: pravdareplikanta"
APP_ID = 85455
APP_SLUG = "cloudflare-workers-and-pages"
MAX_AGE_DAYS = 14


def github(path: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GitHub runner token is missing")
    request = Request(
        "https://api.github.com/repos/" + REPOSITORY + "/" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ReplicantPravda-Announcement",
        },
    )
    try:
        return json.loads(request_bytes(request))
    except HTTPError as error:
        raise ValueError(f"GitHub check failed (HTTP {error.code})") from None
    except (URLError, OSError, ValueError):
        raise ValueError("GitHub response could not be verified") from None


def cloudflare_success(checks: list[dict]) -> bool:
    matching = [
        check
        for check in checks
        if check.get("name") == CHECK_NAME
        and check.get("app", {}).get("id") == APP_ID
        and check.get("app", {}).get("slug") == APP_SLUG
    ]
    if not matching:
        return False
    latest = max(matching, key=lambda check: check["id"])
    return latest.get("status") == "completed" and latest.get("conclusion") == "success"


def verify_context(event: dict, event_name: str, sha: str, *, dry_run: bool) -> bool:
    if event.get("repository", {}).get("full_name") != REPOSITORY:
        return False
    if event_name == "workflow_dispatch":
        return dry_run or os.environ.get("GITHUB_REF") == "refs/heads/main"
    return (
        event_name == "push" and event.get("ref") == "refs/heads/main" and event.get("after") == sha
    )


def wait_for_deployment(sha: str) -> None:
    for attempt in range(32):
        if current_commit() != sha:
            raise ValueError("Production commit changed; no announcement was sent")
        checks = github("commits/" + sha + "/check-runs?filter=latest")["check_runs"]
        if cloudflare_success(checks):
            return
        matching = [
            check
            for check in checks
            if check.get("name") == CHECK_NAME and check.get("app", {}).get("id") == APP_ID
        ]
        if matching and max(matching, key=lambda check: check["id"]).get("status") == "completed":
            raise ValueError("Cloudflare deployment did not succeed; no announcement was sent")
        if attempt < 31:
            time.sleep(15)
    raise ValueError("Timed out waiting for Cloudflare; no announcement was sent")


def read_release(root: Path, manifest_path: Path) -> tuple[dict, dict]:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("site_url") != PRODUCTION_ORIGIN:
        raise ValueError("Announcement release has a different production origin")
    if not manifest.get("issues") or any(
        i.get("status") not in {"approved", "published"} for i in manifest["issues"]
    ):
        raise ValueError("Announcement release contains an unfinished issue")
    packet = validate_announcement(json.loads((root / "announcement.json").read_text()))
    latest = max(
        (issue for issue in manifest["issues"] if issue.get("edition", "engineer") == "engineer"),
        key=lambda issue: date.fromisoformat(issue["issue_id"]),
    )
    if any(packet[key] != latest[key] for key in ("issue_id", "number", "revision", "status")):
        raise ValueError("Announcement differs from the latest released issue")
    expected = manifest.get("files", {}).get("announcement.json")
    if hashlib.sha256((root / "announcement.json").read_bytes()).hexdigest() != expected:
        raise ValueError("Announcement is not covered by the reviewed release manifest")
    return packet, manifest


def fetch_public(url: str) -> bytes:
    if not url.startswith(PRODUCTION_ORIGIN + "/"):
        raise ValueError("Unexpected public verification origin")
    # curl matches the existing site checks and avoids platform-specific bot challenges.
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "25",
            "--max-filesize",
            str(25 * 1024 * 1024),
            "--proto",
            "=https",
            "--write-out",
            "\n%{http_code}",
            "--header",
            "Cache-Control: no-cache",
            url,
        ],
        capture_output=True,
    )
    if result.returncode or not result.stdout.endswith(b"\n200"):
        raise ValueError("Published release is unavailable; no announcement was sent")
    return result.stdout[:-4]


def verify_live(packet: dict, manifest: dict) -> None:
    prefix = "ru/issues/" + packet["issue_id"] + "/"
    for path in ("announcement.json", prefix + "index.html", prefix + "edition.pdf"):
        expected = manifest.get("files", {}).get(path)
        # Workers canonicalizes index.html to its directory URL with a redirect.
        route = path.removesuffix("index.html")
        if (
            not expected
            or hashlib.sha256(fetch_public(PRODUCTION_ORIGIN + "/" + route)).hexdigest() != expected
        ):
            raise ValueError("Published files do not match this release; no announcement was sent")


def current_commit() -> str:
    tip = github("git/ref/heads/main")["object"]["sha"]
    checked_out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if tip != checked_out or not re.fullmatch(r"[0-9a-f]{40}", tip):
        raise ValueError("Stale or non-production checkout; no announcement was sent")
    return tip


def output(values: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a") as stream:
            for key, value in values.items():
                if not re.fullmatch(r"[a-z_]+", key) or "\n" in value or "\r" in value:
                    raise ValueError("Invalid workflow output")
                stream.write(f"{key}={value}\n")


def prepare(root: Path, manifest_path: Path, work: Path, *, dry_run: bool) -> dict:
    sha = current_commit()
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    if not verify_context(event, os.environ["GITHUB_EVENT_NAME"], sha, dry_run=dry_run):
        return {"send": "false", "reason": "Not the successful production deployment"}
    packet, manifest = read_release(root, manifest_path)
    if dry_run:
        print(json.dumps({"preview": packet["text"]}, ensure_ascii=False))
        return {"send": "false", "reason": "Preview only"}
    if os.environ.get("TELEGRAM_ANNOUNCEMENTS_ENABLED") != "true":
        raise ValueError("Automatic announcements are not enabled")
    validate_bot_token(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    age = (today - date.fromisoformat(packet["issue_id"])).days
    if not 0 <= age <= MAX_AGE_DAYS:
        return {
            "send": "false",
            "reason": "Issue is future-dated or outside the automatic announcement window",
        }
    artifact_name = "telegram-issue-" + packet["issue_id"]
    artifacts = github("actions/artifacts?" + urlencode({"name": artifact_name, "per_page": 100}))
    if artifacts.get("artifacts"):
        return {
            "send": "false",
            "reason": "Issue already announced or reserved; check the prior run before retrying",
        }
    wait_for_deployment(sha)
    verify_live(packet, manifest)
    work.mkdir(parents=True, exist_ok=False)
    (work / "packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
    (work / "claim.json").write_text(
        json.dumps({"issue_id": packet["issue_id"], "commit": sha, "state": "reserved"}) + "\n"
    )
    return {"send": "true", "artifact_name": artifact_name}


def send(root: Path, manifest_path: Path, work: Path) -> None:
    if os.environ.get("TELEGRAM_ANNOUNCEMENTS_ENABLED") != "true":
        raise ValueError("Automatic announcements are not enabled")
    claim = json.loads((work / "claim.json").read_text())
    sha = current_commit()
    if claim.get("commit") != sha:
        raise ValueError("Release changed after reservation; no announcement was sent")
    packet, manifest = read_release(root, manifest_path)
    if packet != json.loads((work / "packet.json").read_text()) or packet["issue_id"] != claim.get(
        "issue_id"
    ):
        raise ValueError("Announcement changed after reservation")
    name = "telegram-issue-" + packet["issue_id"]
    artifacts = github("actions/artifacts?" + urlencode({"name": name, "per_page": 100})).get(
        "artifacts", []
    )
    if not artifacts:
        raise ValueError("Durable issue reservation is missing; no announcement was sent")
    if not cloudflare_success(github("commits/" + sha + "/check-runs?filter=latest")["check_runs"]):
        raise ValueError("Cloudflare deployment status changed; no announcement was sent")
    verify_live(packet, manifest)
    with (work / "attempted.json").open("x") as stream:
        stream.write(json.dumps({"issue_id": packet["issue_id"], "commit": sha}) + "\n")
    send_announcement(packet, os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    print("Telegram announcement confirmed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "send", "check-bot"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", type=Path, default=Path("public"))
    parser.add_argument("--manifest", type=Path, default=Path("public.release.json"))
    parser.add_argument("--work", type=Path, default=Path(".telegram-work"))
    args = parser.parse_args()
    try:
        if args.phase == "check-bot":
            check_bot(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
            print("Bot credentials and channel posting permissions verified; no message sent")
        elif args.phase == "prepare":
            values = prepare(args.root, args.manifest, args.work, dry_run=args.dry_run)
            output(values)
            print(json.dumps(values))
        elif args.dry_run:
            raise ValueError("Use prepare --dry-run for previews")
        else:
            send(args.root, args.manifest, args.work)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Do not print arbitrary exception/server content: Bot API URLs contain secrets.
        print(
            "Announcement step failed. No automatic retry; inspect the channel before retrying a reserved issue."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
