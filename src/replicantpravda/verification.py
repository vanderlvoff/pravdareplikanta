"""Output checks independent of the HTML renderer."""

import hashlib
import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from .models import Issue
from .readers import reader_base, reader_groups, reader_issue_key, source_path


def normalized(text: str) -> str:
    return "".join(text.split())


def normalize_pdf(path: Path) -> None:
    """Remove Chromium's wall-clock timestamps for repeatable local artifacts."""
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("Install PDF support: python -m pip install -e '.[pdf]'") from error
    with pymupdf.open(path) as document:
        for page in document:
            for link in page.get_links():
                if urlsplit(link.get("uri", "")).hostname in {"127.0.0.1", "localhost"}:
                    page.delete_link(link)
        metadata = document.metadata
        metadata["creationDate"] = ""
        metadata["modDate"] = ""
        document.set_metadata(metadata)
        data = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    path.write_bytes(data)


def verify_pdf(
    path: Path,
    issue: Issue,
    lang: str,
    *,
    rasterize: bool = False,
    require_article_fonts: bool = False,
) -> dict:
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("Install PDF support: python -m pip install -e '.[pdf]'") from error
    errors = []
    layout_path = path.with_name("pagination.json")
    layout = json.loads(layout_path.read_text(encoding="utf-8")) if layout_path.exists() else None
    with pymupdf.open(path) as document:
        if not len(document):
            errors.append("PDF has no pages")
        if layout and len(document) != layout["page_count"]:
            errors.append("PDF page count differs from measured pagination")
        pages = []
        fonts = {}
        for number, page in enumerate(document, start=1):
            if abs(page.rect.width - 595.276) > 1 or abs(page.rect.height - 841.89) > 1:
                errors.append(f"Page {number}: expected A4")
            text = page.get_text()
            if "\ufffd" in text or "\x00" in text:
                errors.append(f"Page {number}: missing or unextractable glyph")
            for word in page.get_text("words"):
                if (
                    word[0] < 0
                    or word[1] < 0
                    or word[2] > page.rect.width + 1
                    or word[3] > page.rect.height + 1
                ):
                    errors.append(f"Page {number}: text outside page")
                    break
            for font in page.get_fonts():
                xref, name = font[0], font[3]
                if font[2] == "Type3":
                    # Chromium can embed weather symbols as Type3 glyph programs.
                    fonts[f"Type3-{xref}"] = document.xref_get_key(xref, "CharProcs")[0] != "null"
                else:
                    fonts[name] = bool(document.extract_font(xref)[3])
            for article in issue.languages[lang].articles:
                if layout:
                    for fragment in layout["articles"].get(article.id, []):
                        if fragment["page"] == number and normalized(
                            fragment["text"]
                        ) not in normalized(text):
                            errors.append(f"Page {number}: missing article text ({article.id})")
                    continue
                if article.print_page != number:
                    continue
                required = [article.headline, article.dek]
                for block in article.body:
                    required.extend(block.items if block.type == "list" else [block.text])
                for value in required:
                    if normalized(value) not in normalized(text):
                        errors.append(f"Page {number}: missing article text ({article.id})")
                        break
            for mandatory in (str(issue.publication_date), issue.languages[lang].title):
                if normalized(mandatory) not in normalized(text):
                    errors.append(f"Page {number}: missing date or edition title")
            edition = issue.languages[lang]
            if number == 1 and edition.issue_title:
                for value in (edition.issue_title, edition.editorial_note):
                    if normalized(value) not in normalized(text):
                        errors.append("Page 1: missing imported issue title or lead")
            if rasterize:
                page.get_pixmap(dpi=110).save(path.parent / f"page-{number}.png")
            pages.append(
                {
                    "page": number,
                    "width_pt": page.rect.width,
                    "height_pt": page.rect.height,
                    "text_characters": len(text),
                }
            )
        expected_images = sorted(
            (article.id, "/" + article.image.path)
            for article in issue.languages[lang].articles
            if article.image
        )
        if expected_images:
            if (
                not layout
                or sorted((image["article"], image["src"]) for image in layout.get("images", []))
                != expected_images
            ):
                errors.append("PDF illustration placement differs from source")
            for article in issue.languages[lang].articles:
                if article.image and normalized(article.image.caption) not in normalized(
                    "".join(page.get_text() for page in document)
                ):
                    errors.append(f"Missing illustration caption ({article.id})")
        # Verify source coverage independently of page assignments and fragment boundaries.
        if layout and "glossary_cards" in layout:
            from .glossary import glossary_entries

            entries = glossary_entries(issue.languages[lang])
            cards = layout["glossary_cards"]
            if [card["index"] for card in cards] != list(range(1, len(entries) + 1)):
                errors.append("Glossary cards differ from source term order/count")
            elif any(
                normalized(entry.term) not in normalized(card["term"])
                or normalized(entry.definition) != normalized(card["definition"])
                for entry, card in zip(entries, cards, strict=True)
            ):
                errors.append("Glossary card text differs from source")
        all_text = normalized("".join(page.get_text() for page in document))
        expected_ids = {article.id for article in issue.languages[lang].articles}
        if layout and set(layout["articles"]) != expected_ids:
            errors.append("Pagination article IDs differ from source")
        for article in issue.languages[lang].articles:
            article_text = (
                normalized("".join(part["text"] for part in layout["articles"].get(article.id, [])))
                if layout
                else all_text
            )
            required = [article.headline, article.dek]
            for block in article.body:
                required.extend(block.items if block.type == "list" else [block.text])
            if any(normalized(value) not in article_text for value in required):
                errors.append(f"Missing article text ({article.id})")
        expected_font = "ZenKurenaido" if lang == "ja" else "Caveat"
        if not any(expected_font in name and embedded for name, embedded in fonts.items()):
            errors.append(f"{expected_font} motto font is not embedded")
        if require_article_fonts:
            expected_article = "NotoSerifJP" if lang == "ja" else "PTSerif"
            for weight in ("Regular", "Bold"):
                if not any(
                    f"{expected_article}-{weight}" in name and embedded
                    for name, embedded in fonts.items()
                ):
                    errors.append(f"{expected_article}-{weight} article font is not embedded")
        if any(not embedded for embedded in fonts.values()):
            errors.append("Some PDF fonts are not embedded")
    return {
        "passed": not errors,
        "page_count": len(pages),
        "pages": pages,
        "fonts_embedded": fonts,
        "errors": errors,
    }


def artifact_hashes(site: Path) -> dict[str, str]:
    return {
        str(path.relative_to(site)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(site.rglob("*"))
        if path.is_file() and path.name not in {"verification.json", "artifacts.json"}
    }


class PageLinks(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.head_links: list[dict[str, str | None]] = []
        self.language: str | None = None
        self.reader_edition: str = "engineer"
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.language = values.get("lang")
        if tag == "body":
            self.reader_edition = values.get("data-reader-edition") or "engineer"
        if tag == "link":
            self.head_links.append(values)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag in {"a", "link"} and values.get("href"):
            self.hrefs.append(values["href"])


def verify_site_links(site: Path) -> list[str]:
    """Check local page/PDF links and fragment targets, including archived articles."""
    root = site.resolve()
    config = root / "site.json"
    origin = (
        urlsplit(json.loads(config.read_text(encoding="utf-8"))["site_url"])
        if config.exists()
        else None
    )
    pages = {path: PageLinks(path.read_text(encoding="utf-8")) for path in root.rglob("*.html")}
    errors = []
    for path, page in pages.items():
        for href in page.hrefs:
            url = urlsplit(href)
            if (url.scheme or url.netloc) and (
                not origin or (url.scheme, url.netloc) != (origin.scheme, origin.netloc)
            ):
                continue
            target = (
                root / unquote(url.path).lstrip("/")
                if url.path.startswith("/")
                else path.parent / unquote(url.path)
                if url.path
                else path
            ).resolve()
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(root) or not target.is_file():
                errors.append(f"{path.relative_to(root)}: missing local target {href}")
            elif (
                url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids
            ):
                errors.append(f"{path.relative_to(root)}: missing fragment {href}")
    return sorted(errors)


def verify_discovery(site: Path, issues: list[Issue]) -> list[str]:
    """Check metadata reciprocity, stable RSS destinations and eligible sitemap URLs."""
    config = site / "site.json"
    if not config.exists():
        return []  # Snapshots built before discovery metadata was implemented.
    from .discovery import (
        ATOM_NS,
        PUBLIC_STATUSES,
        SITEMAP_NS,
        article_guid,
        article_path,
        sitemap_paths,
    )

    origin = json.loads(config.read_text(encoding="utf-8"))["site_url"]
    errors = []
    pages = {}
    for path in site.rglob("*.html"):
        page = PageLinks(path.read_text(encoding="utf-8"))
        canonical = [link.get("href") for link in page.head_links if link.get("rel") == "canonical"]
        alternates = {
            link.get("hreflang"): link.get("href")
            for link in page.head_links
            if link.get("rel") == "alternate" and link.get("hreflang")
        }
        feeds = [
            link.get("href")
            for link in page.head_links
            if link.get("type") == "application/rss+xml"
        ]
        if (
            len(canonical) != 1
            or set(alternates) != {"ru", "en", "ja"}
            or canonical[0] != alternates.get(page.language)
            or feeds != [f"{origin}{reader_base(page.language, page.reader_edition)}rss.xml"]
            or any(not url or not url.startswith(origin + "/") for url in alternates.values())
        ):
            errors.append(f"{path.relative_to(site)}: inconsistent canonical/hreflang/RSS metadata")
        pages[path.resolve()] = alternates
    for path, alternates in pages.items():
        for url in alternates.values():
            if not url or not url.startswith(origin + "/"):
                continue
            target = (site / url.removeprefix(origin).lstrip("/") / "index.html").resolve()
            if pages.get(target) != alternates:
                errors.append(f"{path.relative_to(site.resolve())}: nonreciprocal hreflang {url}")
    for code, selected in reader_groups(issues).items():
        for lang in ("ru", "en", "ja"):
            base = reader_base(lang, code)
            try:
                rss = ET.parse(site / (base.lstrip("/") + "rss.xml")).getroot()
            except (ET.ParseError, OSError):
                errors.append(f"{base}rss.xml: missing or invalid XML")
                continue
            expected = [
                origin + article_path(issue, lang, article)
                for issue in selected
                if issue.status in PUBLIC_STATUSES
                for article in issue.languages[lang].articles
                if article.id != "glossary"
            ]
            expected_guids = [
                article_guid(issue, lang, article)
                for issue in selected
                if issue.status in PUBLIC_STATUSES
                for article in issue.languages[lang].articles
                if article.id != "glossary"
            ]
            items = rss.findall("channel/item")
            self_link = rss.find(f"channel/{{{ATOM_NS}}}link")
            if (
                rss.tag != "rss"
                or rss.get("version") != "2.0"
                or rss.findtext("channel/language") != lang
                or self_link is None
                or self_link.get("href") != f"{origin}{base}rss.xml"
                or [item.findtext("link") for item in items] != expected
                or [item.findtext("guid") for item in items] != expected_guids
            ):
                errors.append(
                    f"{base}rss.xml: RSS destinations differ from eligible source articles"
                )
    sitemap = site / "sitemap.xml"
    expected_urls = [origin + path for path in sitemap_paths(issues)]
    if not expected_urls:
        if sitemap.exists():
            errors.append("sitemap.xml: no approved or published pages are eligible")
    else:
        try:
            tree = ET.parse(sitemap).getroot()
            if (
                tree.tag != f"{{{SITEMAP_NS}}}urlset"
                or [entry.findtext(f"{{{SITEMAP_NS}}}loc") for entry in tree] != expected_urls
            ):
                errors.append("sitemap.xml: URLs differ from eligible canonical pages")
        except (ET.ParseError, OSError):
            errors.append("sitemap.xml: missing or invalid XML")
    return sorted(errors)


def verify_snapshot(site: Path, issue_id: str) -> dict:
    expected = json.loads((site / "artifacts.json").read_text(encoding="utf-8"))
    if artifact_hashes(site) != expected:
        raise ValueError("Snapshot files changed or are missing; rebuild before review")
    issue = Issue.model_validate_json((site / "source.json").read_text(encoding="utf-8"))
    if str(issue.issue_id) != issue_id:
        raise ValueError("Snapshot issue ID differs from requested issue")
    archive_path = site / "archive.json"
    archive = (
        json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else None
    )
    issues = [issue]
    if archive:
        if archive["latest"] != issue_id:
            raise ValueError("Archive latest issue differs from requested issue")
        issues = [
            Issue.model_validate_json(
                (
                    site
                    / "sources"
                    / ("" if issue.edition == "engineer" else issue.edition)
                    / f"{date.fromisoformat(entry['issue_id'])}.json"
                ).read_text(encoding="utf-8")
            )
            for entry in archive["issues"]
        ]
        from .archive import archive_metadata, collect_issues

        history = tuple(entry for entry in issues if str(entry.issue_id) != issue_id)
        selected = collect_issues(issue, history)
        if [archive_metadata(entry) for entry in selected] != archive["issues"] or not any(
            entry == issue for entry in issues
        ):
            raise ValueError("Archive sources differ from the selected issue metadata")
    registry_path = site / "reader-editions.json"
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry["primary"] != issue.edition:
            raise ValueError("Reader registry primary edition differs from snapshot source")
        all_issues = []
        for code, paths in registry["editions"].items():
            for path in paths:
                target = (site / path).resolve()
                if not target.is_relative_to(site.resolve()):
                    raise ValueError("Unsafe reader source path")
                entry = Issue.model_validate_json(target.read_text(encoding="utf-8"))
                if entry.edition != code or source_path(entry) != path:
                    raise ValueError("Reader registry/source edition mismatch")
                all_issues.append(entry)
        selected_groups = reader_groups(all_issues)
        if selected_groups.get(issue.edition) != issues:
            raise ValueError("Reader registry differs from primary archive")
        issues = [entry for selected in selected_groups.values() for entry in selected]
    report = {"issue_id": issue_id, "editions": {}, "archive": {}}
    pdf = archive["pdf"] if archive else True
    for entry in issues:
        editions = {}
        if pdf:
            for lang in ("ru", "en", "ja"):
                path = (
                    site
                    / reader_base(lang, entry.edition).lstrip("/")
                    / "issues"
                    / str(entry.issue_id)
                    / "edition.pdf"
                )
                editions[lang] = verify_pdf(
                    path,
                    entry,
                    lang,
                    require_article_fonts=(
                        site / "assets/fonts/PTSerif/PTSerif-Regular.ttf"
                    ).is_file(),
                )
        report["archive"][reader_issue_key(entry)] = editions
        if str(entry.issue_id) == issue_id and entry.edition == issue.edition:
            report["editions"] = editions
    report["link_errors"] = verify_site_links(site)
    report["metadata_errors"] = verify_discovery(site, issues)
    report["passed"] = (
        not report["link_errors"]
        and not report["metadata_errors"]
        and all(
            edition["passed"]
            for editions in report["archive"].values()
            for edition in editions.values()
        )
    )
    report["visual_approval"] = "PENDING"
    report["publication"] = "DISABLED"
    return report
