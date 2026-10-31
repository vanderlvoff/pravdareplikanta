"""Offline RSS and sitemap output with explicit origin and editorial eligibility."""

from datetime import datetime, time
from email.utils import format_datetime
from html import escape
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from pydantic import HttpUrl

from .models import Article, Issue
from .readers import reader_base, reader_groups

DEFAULT_SITE_URL = "https://repravda.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ATOM_NS = "http://www.w3.org/2005/Atom"
PUBLIC_STATUSES = {"approved", "published"}

ET.register_namespace("", SITEMAP_NS)
ET.register_namespace("atom", ATOM_NS)


def normalize_site_url(value: str) -> str:
    """Accept only an HTTP(S) origin, never credentials, paths or URL parameters."""
    if any(ord(char) <= 32 for char in value) or "\\" in value:
        raise ValueError("Site URL must be an absolute HTTP(S) origin without whitespace")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
    ):
        raise ValueError(
            "Site URL must be an HTTP(S) origin without credentials, path or parameters"
        )
    return str(HttpUrl(value)).rstrip("/")


def article_path(issue: Issue, lang: str, article: Article) -> str:
    return f"{reader_base(lang, issue.edition)}issues/{issue.issue_id}/articles/{article.slug}/"


def article_guid(issue: Issue, lang: str, article: Article) -> str:
    audience = "" if issue.edition == "engineer" else f"{issue.edition}:"
    return f"replicantpravda:{audience}{issue.issue_id}:{lang}:{article.id}"


def article_excerpt(article: Article) -> str:
    text = article.dek or next(
        (block.text for block in article.body if block.type == "paragraph"), article.headline
    )
    return " ".join(text.split())


def sitemap_paths(issues: list[Issue]) -> list[str]:
    """Exclude aliases, print proofs, and pages containing unapproved issue content."""
    paths = []
    for code, selected in reader_groups(issues).items():
        eligible = [issue for issue in selected if issue.status in PUBLIC_STATUSES]
        for lang in ("ru", "en", "ja"):
            base = reader_base(lang, code)
            if selected[0].status in PUBLIC_STATUSES:
                paths.append(base)
                paths.append(base + "about/")
            if len(eligible) == len(selected):
                paths.append(base + "archive/")
            for issue in eligible:
                paths.append(f"{base}issues/{issue.issue_id}/")
                paths.extend(
                    article_path(issue, lang, article) for article in issue.languages[lang].articles
                )
    return sorted(paths)


def xml_text(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"


def render_sitemap(issues: list[Issue], origin: str) -> str | None:
    paths = sitemap_paths(issues)
    if not paths:
        return None
    if len(paths) > 50000:
        raise ValueError("Sitemap exceeds 50,000 URLs; split it before building")
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for path in paths:
        entry = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(entry, f"{{{SITEMAP_NS}}}loc").text = origin + path
    # The editorial model has no correction timestamp; do not invent lastmod dates.
    xml = xml_text(root)
    if len(xml.encode("utf-8")) > 50 * 1024 * 1024:
        raise ValueError("Sitemap exceeds the 50 MB protocol limit")
    return xml


def render_rss(issues: list[Issue], origin: str, lang: str, labels: dict) -> str:
    base = reader_base(lang, issues[0].edition)
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = issues[0].languages[lang].title
    ET.SubElement(channel, "link").text = origin + base
    ET.SubElement(channel, "description").text = labels["description"]
    ET.SubElement(channel, "language").text = lang
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        href=f"{origin}{base}rss.xml",
        rel="self",
        type="application/rss+xml",
    )
    for issue in issues:
        if issue.status not in PUBLIC_STATUSES:
            continue
        for article in issue.languages[lang].articles:
            if article.id == "glossary":
                continue
            item = ET.SubElement(channel, "item")
            url = origin + article_path(issue, lang, article)
            ET.SubElement(item, "title").text = article.headline
            ET.SubElement(item, "link").text = url
            ET.SubElement(item, "guid", isPermaLink="false").text = article_guid(
                issue, lang, article
            )
            # RSS descriptions may be interpreted as HTML: encode editorial text as literal text.
            ET.SubElement(item, "description").text = escape(article_excerpt(article))
            published = datetime.combine(issue.publication_date, time.min, ZoneInfo("Asia/Tokyo"))
            ET.SubElement(item, "pubDate").text = format_datetime(published)
            ET.SubElement(item, "category").text = labels["categories"][article.category]
    return xml_text(root)
