"""Local command-line interface."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .render import build, load_issue


def main() -> int:
    parser = argparse.ArgumentParser(description="Replicant Pravda offline preview tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("path", type=Path)
    generate = commands.add_parser("build")
    generate.add_argument("--issue", required=True)
    generate.add_argument("--content-dir", type=Path, default=Path("content/issues"))
    generate.add_argument("--output", type=Path, default=Path("dist"))
    preview = commands.add_parser("preview")
    preview.add_argument("--output", type=Path, default=Path("dist"))
    preview.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            issue = load_issue(args.path)
            print(f"Valid issue {issue.issue_id} ({issue.status}); publication disabled")
        elif args.command == "build":
            from datetime import date

            issue_id = date.fromisoformat(args.issue)
            issue = load_issue(args.content_dir / f"{issue_id}.json")
            if issue.issue_id != issue_id:
                raise ValueError("Requested issue ID differs from JSON issue_id")
            build(issue, args.output)
            print(f"Built NON-FINAL local preview: {args.output}")
        else:
            if not (args.output / "verification.json").is_file():
                raise ValueError("Preview requires a generated snapshot")
            handler = partial(SimpleHTTPRequestHandler, directory=str(args.output.resolve()))
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"Local preview: http://127.0.0.1:{args.port}", flush=True)
                server.serve_forever()
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
    except KeyboardInterrupt:
        pass
    return 0
