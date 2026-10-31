"""Install the owner's daily 06:20 launch agent and its isolated Python environment."""

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "com.repravda.daily-publish"
REPOSITORY = "https://github.com/vanderlvoff/pravdareplikanta.git"


def launch_agent(state: Path, node: str, gh: str) -> dict:
    executable_path = ":".join(
        dict.fromkeys(
            [str(Path(node).parent), str(Path(gh).parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        )
    )
    return {
        "Label": LABEL,
        "ProgramArguments": [
            "/usr/bin/caffeinate",
            "-i",
            str(state / "venv/bin/python"),
            str(state / "app/scripts/daily_publish.py"),
            "--state",
            str(state),
            "--push",
        ],
        "WorkingDirectory": str(state),
        "StartCalendarInterval": {"Hour": 6, "Minute": 20},
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": executable_path,
            "TZ": "Asia/Tokyo",
            "PYTHONUNBUFFERED": "1",
            "GIT_TERMINAL_PROMPT": "0",
        },
        "StandardOutPath": str(state / "logs/daily.log"),
        "StandardErrorPath": str(state / "logs/daily-error.log"),
        "ProcessType": "Background",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / "Library/Application Support/ReplicantPravda",
    )
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise ValueError("launchd installation requires macOS")
    node, gh = shutil.which("node"), shutil.which("gh")
    if not node or not gh:
        raise ValueError("Install Node and authenticate GitHub CLI first")
    state = args.state.resolve()
    (state / "logs").mkdir(parents=True, exist_ok=True)
    app = state / "app"
    if not app.exists():
        subprocess.run(["git", "clone", "--branch", "main", REPOSITORY, str(app)], check=True)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=app).strip():
        raise ValueError("Isolated app has local changes; inspect it before installation")
    python = state / "venv/bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(state / "venv")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-e", str(app) + "[pdf]"], check=True)
    subprocess.run([str(python), "-m", "playwright", "install", "chromium"], check=True)
    plist = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    plist.parent.mkdir(parents=True, exist_ok=True)
    if plist.exists():
        shutil.copyfile(plist, plist.with_suffix(".plist.previous"))
    plist.write_bytes(plistlib.dumps(launch_agent(state, node, gh)))
    subprocess.run(["plutil", "-lint", str(plist)], check=True)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain + "/" + LABEL], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)
    print(f"Installed {LABEL}: daily 06:20 Mac local time (configured Asia/Tokyo)")
    print(f"Logs: {state / 'logs'}")


if __name__ == "__main__":
    main()
