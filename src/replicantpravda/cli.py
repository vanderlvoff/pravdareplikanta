"""Local command-line interface."""

import argparse
import json
import os
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

from .models import Issue
from .preview import PreviewServer
from .render import build, load_issue
from .weather import LOCATIONS, Weather, fetch_forecast


def main() -> int:
    parser = argparse.ArgumentParser(description="Replicant Pravda offline preview tools")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("path", type=Path)
    generate = commands.add_parser("build")
    generate.add_argument("--issue", required=True)
    generate.add_argument(
        "--pdf", action="store_true", help="Render and verify automatically paginated A4 editions"
    )
    generate.add_argument("--content-dir", type=Path, default=Path("content/issues"))
    generate.add_argument("--output", type=Path, default=Path("dist"))
    generate.add_argument("--weather", type=Path, help="Saved weather JSON; must match issue date")
    generate.add_argument(
        "--edition-weather",
        action="append",
        default=[],
        metavar="LANG=PATH",
        help="Saved weather override for ru, en or ja (repeatable)",
    )
    weather = commands.add_parser("weather")
    weather.add_argument("--location", choices=tuple(LOCATIONS), default="ichikawa")
    weather.add_argument("--date", required=True, type=date.fromisoformat)
    weather.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--issue", required=True, type=date.fromisoformat)
    verify.add_argument("--output", type=Path, default=Path("dist"))
    draft = commands.add_parser(
        "draft", help="Research and generate a local editorial draft via OpenAI"
    )
    draft.add_argument("--issue", required=True, type=date.fromisoformat)
    draft.add_argument("--number", required=True, type=int)
    draft.add_argument("--since", type=date.fromisoformat)
    draft.add_argument("--model", default=os.environ.get("OPENAI_MODEL", ""))
    draft.add_argument("--template", type=Path, default=Path("content/issues/2026-10-29.json"))
    draft.add_argument("--output", required=True, type=Path)
    draft.add_argument("--max-output-tokens", type=int, default=16000)
    draft.add_argument("--dry-run", action="store_true")
    importer = commands.add_parser("import", help="Import RU/EN/JA daily editorial JSON")
    importer.add_argument("--input", type=Path, default=Path("data/latest"))
    importer.add_argument("--template", type=Path, required=True)
    importer.add_argument("--number", type=int, required=True)
    importer.add_argument("--revision", type=int, default=1)
    importer.add_argument("--output", type=Path, required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("--output", type=Path, default=Path("dist"))
    preview.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            issue = load_issue(args.path)
            print(f"Valid issue {issue.issue_id} ({issue.status}); publication disabled")
        elif args.command == "weather":
            if args.output.exists():
                raise ValueError("Weather output exists; choose a new snapshot path")
            snapshot = (
                fetch_forecast(args.date)
                if args.location == "ichikawa"
                else fetch_forecast(args.date, args.location)
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(snapshot.model_dump_json(indent=2) + "\n")
            print(f"Saved {args.location} forecast: {args.output}")
        elif args.command == "build":
            issue_id = date.fromisoformat(args.issue)
            issue = load_issue(args.content_dir / f"{issue_id}.json")
            if issue.issue_id != issue_id:
                raise ValueError("Requested issue ID differs from JSON issue_id")
            if args.weather:
                weather = Weather.model_validate_json(args.weather.read_text(encoding="utf-8"))
                data = issue.model_dump()
                data["weather"] = weather
                issue = Issue.model_validate(data)
            if args.edition_weather:
                data = issue.model_dump()
                for override in args.edition_weather:
                    language, separator, filename = override.partition("=")
                    if not separator or language not in ("ru", "en", "ja"):
                        raise ValueError("Edition weather must be LANG=PATH with ru, en or ja")
                    data["languages"][language]["weather"] = Weather.model_validate_json(
                        Path(filename).read_text(encoding="utf-8")
                    )
                issue = Issue.model_validate(data)
            build(issue, args.output, pdf=args.pdf)
            print(f"Built NON-FINAL local preview: {args.output}")
        elif args.command == "verify":
            from .verification import verify_snapshot

            report = verify_snapshot(args.output, str(args.issue))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if not report["passed"]:
                return 1
        elif args.command == "draft":
            from .editorial import generate_draft

            report = generate_draft(
                template=load_issue(args.template),
                day=args.issue,
                number=args.number,
                output=args.output,
                model=args.model,
                since=args.since,
                max_output_tokens=args.max_output_tokens,
                dry_run=args.dry_run,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.command == "import":
            from .importer import save_import

            issue = save_import(
                args.input,
                load_issue(args.template),
                args.output,
                number=args.number,
                revision=args.revision,
            )
            print(f"Imported draft {issue.issue_id}: {args.output}")
        else:
            if not (args.output / "verification.json").is_file():
                raise ValueError("Preview requires a generated snapshot")
            handler = partial(SimpleHTTPRequestHandler, directory=str(args.output.resolve()))
            with PreviewServer(("127.0.0.1", args.port), handler) as server:
                print(f"Local preview: http://127.0.0.1:{args.port}", flush=True)
                server.serve_forever()
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")
    except KeyboardInterrupt:
        pass
    return 0
