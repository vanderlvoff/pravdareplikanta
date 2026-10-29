"""Deterministic static rendering; no network or publication operations."""

import json
import shutil
import tempfile
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .models import Issue

LABELS = {
    "en": {
        "archive": "Archive",
        "sources": "Sources",
        "notice": "NON-FINAL · Local preview · Approved artwork and fonts pending",
    },
    "ru": {
        "archive": "Архив",
        "sources": "Источники",
        "notice": "НЕ ФИНАЛ · Локальный просмотр · Ожидаются утверждённые изображения и шрифты",
    },
    "ja": {
        "archive": "アーカイブ",
        "sources": "出典",
        "notice": "非最終版 · ローカルプレビュー · 承認済み画像とフォント待ち",
    },
}


def load_issue(path: Path) -> Issue:
    return Issue.model_validate_json(path.read_text(encoding="utf-8"))


def build(issue: Issue, output: Path) -> None:
    """Build one isolated preview snapshot. Refuse to overwrite existing output."""
    output = output.absolute()
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=PackageLoader("replicantpravda"), autoescape=select_autoescape())
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".rp-build-") as temporary:
        staging = Path(temporary) / "site"
        staging.mkdir()

        def write(path: str, content: str) -> None:
            destination = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        write("style.css", env.loader.get_source(env, "style.css")[0])
        write("index.html", env.get_template("root.html").render())
        for lang, edition in sorted(issue.languages.items()):
            context = dict(issue=issue, lang=lang, edition=edition, labels=LABELS[lang])
            for route in (
                f"{lang}/index.html",
                f"{lang}/archive/index.html",
                f"{lang}/issues/{issue.issue_id}/index.html",
            ):
                write(route, env.get_template("edition.html").render(**context))
            for article in edition.articles:
                translations = {
                    code: next(a.slug for a in other.articles if a.id == article.id)
                    for code, other in issue.languages.items()
                }
                write(
                    f"{lang}/articles/{article.slug}/index.html",
                    env.get_template("article.html").render(
                        **context, article=article, translations=translations
                    ),
                )
        write("robots.txt", "User-agent: *\nDisallow: /\n")
        write(
            "verification.json",
            json.dumps(
                {
                    "issue_id": str(issue.issue_id),
                    "status": issue.status,
                    "preview_only": True,
                    "visual_approval": "BLOCKED: approved assets absent",
                    "pdf": "NOT_IMPLEMENTED",
                    "publication": "DISABLED",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        shutil.move(str(staging), str(output))
