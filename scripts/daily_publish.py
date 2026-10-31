"""Owner-authorized daily Mac runner. Default prepares only; --push publishes main."""

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPOSITORY = "https://github.com/vanderlvoff/pravdareplikanta.git"
PUBLISH_PATHS = ("data", "content/editions", "content/weather", "public", "public.release.json")


def run(command: list[str], cwd: Path, *, capture: bool = False, env: dict | None = None) -> str:
    result = subprocess.run(
        command, cwd=cwd, env=env, check=True, text=True, capture_output=capture
    )
    return result.stdout.strip() if capture else ""


def publish(state: Path, *, push: bool, force: bool = False) -> dict:
    app = state / "app"
    if run(["git", "remote", "get-url", "origin"], app, capture=True) != REPOSITORY:
        raise ValueError("Unexpected automation repository")
    if run(["git", "status", "--porcelain"], app, capture=True):
        raise ValueError("Automation app has local edits; refusing to overwrite them")
    run(["git", "fetch", "origin"], app)
    run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], app)
    run(["git", "reset", "--keep", "origin/main"], app)
    stamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d-%H%M%S")
    output = state / "runs" / stamp
    output.mkdir(parents=True)
    checkout = output / "checkout"
    run(["git", "worktree", "add", "--detach", str(checkout), "origin/main"], app)
    run(["git", "restore", "--source", "origin/develop", "--worktree", "--", "data"], checkout)
    env = dict(os.environ, PYTHONPATH=str(checkout / "src"), GIT_TERMINAL_PROMPT="0")
    command = [sys.executable, "-m", "replicantpravda.daily_build", "--output", str(output)]
    if force:
        command.append("--force")
    run(command, checkout, env=env)
    result = json.loads((output / "result.json").read_text())
    if not result["changed"]:
        print(json.dumps(result), flush=True)
        return result
    run(["node", str(checkout / "scripts/check-public.mjs"), str(output / "public")], checkout)
    # Only the disposable checkout is replaced; prior runs and the live release
    # remain recoverable even when verification, commit, push or deployment fail.
    shutil.rmtree(checkout / "public")
    shutil.copytree(output / "public", checkout / "public")
    shutil.copyfile(output / "public.release.json", checkout / "public.release.json")
    run(["git", "add", "--", *PUBLISH_PATHS], checkout)
    changed = run(["git", "diff", "--cached", "--name-only"], checkout, capture=True).splitlines()
    if not changed or any(
        not any(path == allowed or path.startswith(allowed + "/") for allowed in PUBLISH_PATHS)
        for path in changed
    ):
        raise ValueError("Unexpected publication paths")
    run(
        [
            "git",
            "commit",
            "-m",
            f"Publish issue {result['issue_id']} revision {result['revision']}",
        ],
        checkout,
    )
    result["commit"] = run(["git", "rev-parse", "HEAD"], checkout, capture=True)
    result["pushed"] = False
    if push:
        gh = shutil.which("gh")
        if not gh:
            raise ValueError("GitHub CLI is required for unattended authentication")
        run(
            [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                f"credential.helper=!{gh} auth git-credential",
                "push",
                "origin",
                "HEAD:refs/heads/main",
            ],
            checkout,
            env=env,
        )
        result["pushed"] = True
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (state / "last-run.json").write_text(json.dumps(result | {"run": str(output)}, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with (state / "daily.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Daily publication is already running", flush=True)
            return 0
        try:
            publish(state, push=args.push, force=args.force)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            print(f"Daily publication stopped: {type(error).__name__}", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
