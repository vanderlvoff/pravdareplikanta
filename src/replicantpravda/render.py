"""Deterministic static rendering; no network or publication operations."""

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, select_autoescape

from .archive import archive_metadata, collect_issues
from .assets import copy_assets
from .discovery import (
    DEFAULT_SITE_URL,
    article_excerpt,
    normalize_site_url,
    render_rss,
    render_sitemap,
)
from .models import Issue
from .glossary import glossary_entries
from .annotations import annotate_article
from .readers import reader_base, reader_choices, reader_groups, reader_issue_key, source_path
from .illustrations import copy_illustrations
from .verification import artifact_hashes, verify_discovery, verify_site_links

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
        "read_more": "Read more…",
        "back_to_issue": "Back to issue",
        "issue": "Issue",
        "archive": "Archive",
        "sources": "Sources",
        "notice": "NON-FINAL · Local preview · Full-page visual review pending",
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
        "read_more": "Читать дальше…",
        "back_to_issue": "Назад к выпуску",
        "issue": "Выпуск",
        "archive": "Архив",
        "sources": "Источники",
        "notice": "НЕ ФИНАЛ · Локальный просмотр · Полный макет ожидает визуальной проверки",
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
        "read_more": "続きを読む…",
        "back_to_issue": "紙面に戻る",
        "issue": "号",
        "archive": "アーカイブ",
        "sources": "出典",
        "notice": "非最終版 · ローカルプレビュー · 紙面全体の目視確認待ち",
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
    archive_issues: tuple[Issue, ...] = (),
    site_url: str = DEFAULT_SITE_URL,
    publication: bool = False,
    reader_issues: tuple[Issue, ...] = (),
    import_report: dict | None = None,
) -> None:
    """Build latest and explicitly selected history as one isolated local preview."""
    latest = issue
    primary_issues = collect_issues(latest, archive_issues)
    groups = reader_groups([*primary_issues, *reader_issues])
    issues = [entry for selected in groups.values() for entry in selected]
    if publication and any(entry.status not in {"approved", "published"} for entry in issues):
        raise ValueError("Publication builds require approved/published issues only")
    site_url = normalize_site_url(site_url)
    output = output.absolute()
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=PackageLoader("replicantpravda"), autoescape=select_autoescape())
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".rp-build-") as temporary:
        staging = Path(temporary) / "site"
        staging.mkdir()
        copy_assets(assets, staging / "assets")
        illustration_assets = {}
        for entry in issues:
            illustration_assets.update(copy_illustrations(entry, image_root, staging))
        brand = json.loads(env.loader.get_source(env, "brand.json")[0])
        about = json.loads(env.loader.get_source(env, "about.json")[0])
        archive_labels = json.loads(env.loader.get_source(env, "archive-labels.json")[0])
        discovery_labels = json.loads(env.loader.get_source(env, "discovery-labels.json")[0])
        weather_labels = json.loads(env.loader.get_source(env, "weather-labels.json")[0])
        reader_labels = json.loads(env.loader.get_source(env, "reader-labels.json")[0])
        glossary_labels = json.loads(env.loader.get_source(env, "glossary-labels.json")[0])
        glossary_aliases = json.loads(env.loader.get_source(env, "glossary-aliases.json")[0])
        guide = json.loads(env.loader.get_source(env, "guide.json")[0])

        def write(path: str, content: str) -> None:
            destination = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        if illustration_assets:
            write("illustrations.json", json.dumps(illustration_assets, indent=2) + "\n")
        if import_report is not None:
            write(
                "reader-import.json", json.dumps(import_report, ensure_ascii=False, indent=2) + "\n"
            )
        style = env.loader.get_source(env, "style.css")[0]
        write("style.css", style)
        style_version = hashlib.sha256(style.encode()).hexdigest()[:12]

        sitemap = render_sitemap(issues, site_url)
        if sitemap:
            write("sitemap.xml", sitemap)
        for code, selected in groups.items():
            for lang in ("ru", "en", "ja"):
                write(
                    reader_base(lang, code).lstrip("/") + "rss.xml",
                    render_rss(selected, site_url, lang, discovery_labels[lang]),
                )
        write(
            "site.json",
            json.dumps(
                {
                    "site_url": site_url,
                    "sitemap": bool(sitemap),
                    "preview_only": not publication,
                },
                indent=2,
            )
            + "\n",
        )

        for issue in issues:
            selected = groups[issue.edition]
            edition_latest = selected[0]
            write(source_path(issue), issue.model_dump_json(indent=2) + "\n")
            for lang, edition in sorted(issue.languages.items()):
                terms = glossary_entries(edition)
                base = reader_base(lang, issue.edition)
                words = reader_labels[lang]
                labels = LABELS[lang] | (
                    words["children_labels"] if issue.edition == "children" else {}
                )
                archive_words = archive_labels[lang] | (
                    {"intro": words["children_archive_intro"], "home": words["children_home"]}
                    if issue.edition == "children"
                    else {}
                )

                def navigation(page: str, article_id: str | None = None) -> list[dict]:
                    return reader_choices(
                        groups,
                        lang,
                        issue.edition,
                        words,
                        page=page,
                        issue_date=issue.issue_id,
                        article_id=article_id,
                    )

                current_weather = edition.weather or issue.weather
                location = (
                    current_weather.location
                    if current_weather
                    else {"ru": "ichikawa", "en": "breukelen", "ja": "smolensk"}[lang]
                )
                context = dict(
                    issue=issue,
                    preview_only=not publication,
                    site_url=site_url,
                    discovery_labels=discovery_labels[lang],
                    page_title=f"{edition.issue_title or issue.issue_id} · {edition.title}",
                    page_description=edition.editorial_note
                    or discovery_labels[lang]["description"],
                    language_links={
                        code: f"{reader_base(code, issue.edition)}issues/{issue.issue_id}/"
                        for code in issue.languages
                    },
                    reader_base=base,
                    reader_code=issue.edition,
                    reader_labels=words,
                    reader_name=words["editions"][issue.edition],
                    reader_choices=navigation("issue"),
                    issue_glossary=terms,
                    glossary_labels=glossary_labels[lang],
                    article_base=f"{base}issues/{issue.issue_id}/articles/",
                    archive_labels=archive_words,
                    lang=lang,
                    edition=edition,
                    illustration_assets=illustration_assets,
                    labels=labels,
                    brand=brand.get(lang),
                    about=about[lang],
                    guide=guide[lang],
                    style_version=style_version,
                    print_enabled=pdf,
                    article_sections=[
                        {
                            "key": key,
                            "title": labels["sections"][key],
                            "articles": [
                                a
                                for a in edition.articles
                                if (a.category == "news") == (key == "news")
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
                write(
                    f"{base}issues/{issue.issue_id}/index.html".lstrip("/"),
                    env.get_template("edition.html").render(**context),
                )
                if issue == edition_latest:
                    write(
                        base.lstrip("/") + "about/index.html",
                        env.get_template("guide.html").render(
                            **(
                                context
                                | {
                                    "is_guide": True,
                                    "page_title": f"{guide[lang]['title']} · {edition.title}",
                                    "page_description": guide[lang]["intro"],
                                    "language_links": {
                                        code: reader_base(code, issue.edition) + "about/"
                                        for code in issue.languages
                                    },
                                    "reader_choices": navigation("about"),
                                    "guide_editions": navigation("home"),
                                }
                            )
                        ),
                    )
                    write(
                        base.lstrip("/") + "index.html",
                        env.get_template("edition.html").render(
                            **(
                                context
                                | {
                                    "language_links": {
                                        code: reader_base(code, issue.edition)
                                        for code in issue.languages
                                    },
                                    "reader_choices": navigation("home"),
                                }
                            )
                        ),
                    )
                    groups_by_year = {}
                    for entry in selected:
                        groups_by_year.setdefault(entry.publication_date.year, []).append(entry)
                    write(
                        base.lstrip("/") + "archive/index.html",
                        env.get_template("archive.html").render(
                            **(
                                context
                                | {
                                    "archive_groups": groups_by_year,
                                    "latest_id": edition_latest.issue_id,
                                    "page_title": f"{labels['archive']} · {words['editions'][issue.edition]} · {edition.title}",
                                    "page_description": archive_words["intro"],
                                    "language_links": {
                                        code: reader_base(code, issue.edition) + "archive/"
                                        for code in issue.languages
                                    },
                                    "reader_choices": navigation("archive"),
                                    "is_archive": True,
                                }
                            )
                        ),
                    )
                if pdf:
                    write(
                        f"{base}issues/{issue.issue_id}/print/index.html".lstrip("/"),
                        env.get_template("print.html").render(**context),
                    )
                for article in edition.articles:
                    translations = {
                        code: next(a.slug for a in other.articles if a.id == article.id)
                        for code, other in issue.languages.items()
                    }
                    html = env.get_template("article.html").render(
                        **(
                            context
                            | {
                                "article": article,
                                **annotate_article(
                                    article,
                                    terms,
                                    lang,
                                    glossary_aliases[lang],
                                    glossary_labels[lang]["reference"],
                                ),
                                "page_title": f"{article.headline} · {edition.title}",
                                "page_description": article_excerpt(article),
                                "language_links": {
                                    code: f"{reader_base(code, issue.edition)}issues/{issue.issue_id}/articles/{slug}/"
                                    for code, slug in translations.items()
                                },
                                "reader_choices": navigation("article", article.id),
                            }
                        )
                    )
                    write(
                        f"{base}issues/{issue.issue_id}/articles/{article.slug}/index.html".lstrip(
                            "/"
                        ),
                        html,
                    )
                    # Preserve old bookmarks; a repeated slug resolves to its newest edition.
                    alias = f"{base}articles/{article.slug}/index.html".lstrip("/")
                    if not (staging / alias).exists():
                        write(alias, html)
        write(
            "index.html",
            (staging / (reader_base("ru", latest.edition).lstrip("/") + "index.html")).read_text(
                encoding="utf-8"
            ),
        )
        write(
            "robots.txt",
            ("User-agent: *\nAllow: /\n" if publication else "User-agent: *\nDisallow: /\n")
            + (f"\nSitemap: {site_url}/sitemap.xml\n" if sitemap else ""),
        )
        issue = latest
        write("source.json", latest.model_dump_json(indent=2) + "\n")
        write(
            "archive.json",
            json.dumps(
                {
                    "latest": str(latest.issue_id),
                    "pdf": pdf,
                    "issues": [archive_metadata(entry) for entry in primary_issues],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        write(
            "reader-editions.json",
            json.dumps(
                {
                    "primary": latest.edition,
                    "editions": {
                        code: [source_path(entry) for entry in selected]
                        for code, selected in groups.items()
                    },
                },
                indent=2,
            )
            + "\n",
        )
        print_report = None
        archive_print_reports = {}
        if pdf:
            from .pdf import PrintFailure, render_pdfs

            write("paginate.js", env.loader.get_source(env, "paginate.js")[0])
            write("print.css", env.loader.get_source(env, "print.css")[0])
            try:
                for entry in issues:
                    archive_print_reports[reader_issue_key(entry)] = render_pdfs(staging, entry)
                print_report = archive_print_reports[reader_issue_key(latest)]
                for code, selected in groups.items():
                    for lang in selected[0].languages:
                        base = reader_base(lang, code).lstrip("/")
                        write(
                            base + "print/index.html",
                            (
                                staging
                                / base
                                / "issues"
                                / str(selected[0].issue_id)
                                / "print/index.html"
                            ).read_text(encoding="utf-8"),
                        )
            except PrintFailure as error:
                error.report["issue_id"] = str(entry.issue_id)
                error.report["reader_edition"] = entry.edition
                failed_path = output.parent / f"{output.name}.failed.json"
                failed_path.write_text(
                    json.dumps(error.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                raise ValueError(
                    f"Print overflow/verification failed; report: {failed_path}"
                ) from error
        link_errors = verify_site_links(staging)
        if link_errors:
            raise ValueError("Broken snapshot links: " + "; ".join(link_errors[:10]))
        metadata_errors = verify_discovery(staging, issues)
        if metadata_errors:
            raise ValueError("Invalid discovery metadata: " + "; ".join(metadata_errors[:10]))
        write(
            "verification.json",
            json.dumps(
                {
                    "issue_id": str(issue.issue_id),
                    "status": issue.status,
                    "link_errors": link_errors,
                    "metadata_errors": metadata_errors,
                    "archive": {
                        "issues": [archive_metadata(entry) for entry in issues],
                        "pdf": archive_print_reports if pdf else "NOT_REQUESTED",
                    },
                    "preview_only": not publication,
                    "visual_approval": "PENDING: supplied header assets; full-page references and review required",
                    "pdf": print_report if pdf else "NOT_REQUESTED",
                    "publication": "READY_FOR_UPLOAD_REVIEW" if publication else "DISABLED",
                    "weather": issue.weather.kind if issue.weather else "MISSING",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        write("artifacts.json", json.dumps(artifact_hashes(staging), indent=2) + "\n")
        shutil.move(str(staging), str(output))
