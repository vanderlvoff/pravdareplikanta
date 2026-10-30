"""Deterministic static rendering; no network or publication operations."""

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, select_autoescape

from .assets import copy_assets
from .models import Issue
from .illustrations import copy_illustrations
from .verification import artifact_hashes

LABELS = {
    "en": {
        "proof": "NON-FINAL",
        "generated_illustration": "AI-generated illustration",
        "pdf": "PDF edition · A4",
        "kicker": "Physical AI — the path to a beautiful tomorrow.",
        "sections": {"news": "News", "analysis": "Analysis"},
        "article_kinds": {"opinion": "Opinion", "satire": "Satire"},
        "translated_title": "THE REPLICANT TRUTH",
        "strapline": "A NEWSPAPER ABOUT PHYSICAL ARTIFICIAL INTELLIGENCE",
        "weather": "Weather",
        "weather_pending": "Forecast not supplied",
        "issue": "Issue",
        "archive": "Archive",
        "sources": "Sources",
        "notice": "NON-FINAL · Local preview · Body fonts provisional · Print layout pending",
    },
    "ru": {
        "proof": "ПРОБНЫЙ МАКЕТ",
        "generated_illustration": "Иллюстрация, созданная ИИ",
        "pdf": "PDF выпуска · A4",
        "kicker": "Physical AI — путь в прекрасное далёко.",
        "sections": {"news": "Новости", "analysis": "Анализ"},
        "article_kinds": {"opinion": "Мнение", "satire": "Сатира"},
        "translated_title": "",
        "strapline": "ГАЗЕТА О ФИЗИЧЕСКОМ ИСКУССТВЕННОМ ИНТЕЛЛЕКТЕ",
        "weather": "Погода · Итикава",
        "weather_pending": "Прогноз для выпуска не предоставлен",
        "issue": "Выпуск",
        "archive": "Архив",
        "sources": "Источники",
        "notice": "НЕ ФИНАЛ · Локальный просмотр · Шрифты статей временные · Печатный макет в работе",
    },
    "ja": {
        "proof": "非最終版",
        "generated_illustration": "AI生成イラスト",
        "pdf": "PDF版 · A4",
        "kicker": "Physical AI — 素晴らしい未来への道。",
        "sections": {"news": "ニュース", "analysis": "分析"},
        "article_kinds": {"opinion": "論説", "satire": "風刺"},
        "translated_title": "レプリカントの真実",
        "strapline": "フィジカルAIの新聞",
        "weather": "天気",
        "weather_pending": "予報データ未提供",
        "issue": "号",
        "archive": "アーカイブ",
        "sources": "出典",
        "notice": "非最終版 · ローカルプレビュー · 本文フォントは仮設定 · 印刷レイアウト準備中",
    },
}


def load_issue(path: Path) -> Issue:
    return Issue.model_validate_json(path.read_text(encoding="utf-8"))


def build(
    issue: Issue,
    output: Path,
    assets: Path = Path("assets"),
    *,
    pdf: bool = False,
    image_root: Path = Path("."),
) -> None:
    """Build one isolated preview snapshot. Refuse to overwrite existing output."""
    output = output.absolute()
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=PackageLoader("replicantpravda"), autoescape=select_autoescape())
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".rp-build-") as temporary:
        staging = Path(temporary) / "site"
        staging.mkdir()
        copy_assets(assets, staging / "assets")
        illustration_assets = copy_illustrations(issue, image_root, staging)
        brand = json.loads(env.loader.get_source(env, "brand.json")[0])
        weather_labels = json.loads(env.loader.get_source(env, "weather-labels.json")[0])

        def write(path: str, content: str) -> None:
            destination = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        if illustration_assets:
            write("illustrations.json", json.dumps(illustration_assets, indent=2) + "\n")
        style = env.loader.get_source(env, "style.css")[0]
        write("style.css", style)
        style_version = hashlib.sha256(style.encode()).hexdigest()[:12]

        for lang, edition in sorted(issue.languages.items()):
            current_weather = edition.weather or issue.weather
            location = (
                current_weather.location
                if current_weather
                else {"ru": "ichikawa", "en": "breukelen", "ja": "smolensk"}[lang]
            )
            context = dict(
                issue=issue,
                lang=lang,
                edition=edition,
                illustration_assets=illustration_assets,
                labels=LABELS[lang],
                brand=brand.get(lang),
                style_version=style_version,
                print_enabled=pdf,
                article_sections=[
                    {
                        "key": key,
                        "title": LABELS[lang]["sections"][key],
                        "articles": [
                            a for a in edition.articles if (a.category == "news") == (key == "news")
                        ],
                    }
                    for key in ("news", "analysis")
                ],
                weather=current_weather,
                weather_city=weather_labels[lang]["cities"][location],
                weather_country=weather_labels[lang].get("countries", {}).get(location, ""),
                weather_timezone=(
                    datetime.fromisoformat(str(current_weather.forecast_date) + "T09:00:00")
                    .replace(tzinfo=ZoneInfo(current_weather.timezone))
                    .strftime("%Z")
                    if current_weather
                    else ""
                ),
                weather_labels=weather_labels[lang],
                weather_retrieved=(
                    current_weather.retrieved_at.astimezone(
                        ZoneInfo(current_weather.timezone)
                    ).strftime("%Y-%m-%d %H:%M %Z")
                    if current_weather
                    else None
                ),
                weather_icons={
                    "clear": "☀",
                    "cloudy": "☁",
                    "fog": "≋",
                    "rain": "☂",
                    "snow": "❄",
                    "storm": "ϟ",
                },
            )
            for route in (
                f"{lang}/index.html",
                f"{lang}/archive/index.html",
                f"{lang}/issues/{issue.issue_id}/index.html",
            ):
                write(route, env.get_template("edition.html").render(**context))
            if pdf:
                write(f"{lang}/print/index.html", env.get_template("print.html").render(**context))
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
        write("index.html", (staging / "ru/index.html").read_text(encoding="utf-8"))
        write("robots.txt", "User-agent: *\nDisallow: /\n")
        print_report = None
        if pdf:
            from .pdf import PrintFailure, render_pdfs

            write("paginate.js", env.loader.get_source(env, "paginate.js")[0])
            write("print.css", env.loader.get_source(env, "print.css")[0])
            write("source.json", issue.model_dump_json(indent=2) + "\n")
            try:
                print_report = render_pdfs(staging, issue)
            except PrintFailure as error:
                failed_path = output.parent / f"{output.name}.failed.json"
                failed_path.write_text(
                    json.dumps(error.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                raise ValueError(
                    f"Print overflow/verification failed; report: {failed_path}"
                ) from error
            write("artifacts.json", json.dumps(artifact_hashes(staging), indent=2) + "\n")
        write(
            "verification.json",
            json.dumps(
                {
                    "issue_id": str(issue.issue_id),
                    "status": issue.status,
                    "preview_only": True,
                    "visual_approval": "PENDING: supplied header assets; full-page references and review required",
                    "pdf": print_report if pdf else "NOT_REQUESTED",
                    "publication": "DISABLED",
                    "weather": issue.weather.kind if issue.weather else "MISSING",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        shutil.move(str(staging), str(output))
