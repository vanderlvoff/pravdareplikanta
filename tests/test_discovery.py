"""RSS, sitemap and HTML metadata must agree on safe, stable multilingual URLs."""

import json
from email.utils import parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from replicantpravda.cli import main
from replicantpravda.discovery import ATOM_NS, SITEMAP_NS, normalize_site_url
from replicantpravda.models import Issue
from replicantpravda.render import build, load_issue
from replicantpravda.verification import (
    PageLinks,
    verify_discovery,
    verify_site_links,
    verify_snapshot,
)

ORIGIN = "https://repravda.com"


def make_issue(day: str, status: str) -> Issue:
    data = load_issue(Path("content/issues/2026-10-29.json")).model_dump(mode="json")
    data.update(issue_id=day, publication_date=day, status=status, weather=None)
    for lang, edition in data["languages"].items():
        edition["weather"] = None
        edition["articles"][0]["headline"] += f" · {day} <&>"
        edition["articles"][0]["dek"] = ""
        edition["articles"][0]["body"][0]["text"] = (
            'Текст / text / 日本語 <script>x</script> & "quote"'
        )
        if lang == "en":
            edition["articles"][0]["slug"] = "english-slug"
        glossary = edition["articles"][1].copy()
        glossary.update(id="glossary", slug="glossary", category="analysis")
        edition["articles"].append(glossary)
    return Issue.model_validate(data)


@pytest.fixture
def issues() -> tuple[Issue, Issue]:
    return make_issue("2026-10-30", "approved"), make_issue("2026-10-31", "published")


def head_links(site: Path, route: str) -> list[dict]:
    return PageLinks((site / route / "index.html").read_text()).head_links


@pytest.mark.parametrize("lang", ["ru", "en", "ja"])
def test_rss_roundtrip_unicode_escaping_dates_and_stable_guids(issues, tmp_path, lang):
    older, latest = issues
    build(latest, tmp_path / "site", archive_issues=(older,))
    rss = ET.parse(tmp_path / "site" / lang / "rss.xml").getroot()
    assert rss.tag == "rss" and rss.attrib == {"version": "2.0"}
    channel = rss.find("channel")
    assert channel.findtext("title") == latest.languages[lang].title
    assert channel.findtext("language") == lang
    assert channel.find(f"{{{ATOM_NS}}}link").attrib == {
        "href": f"{ORIGIN}/{lang}/rss.xml",
        "rel": "self",
        "type": "application/rss+xml",
    }
    items = channel.findall("item")
    assert len(items) == 6  # Three stories per issue; the reference glossary is not a story.
    assert len({item.findtext("guid") for item in items}) == len(items)
    for issue, offset in ((latest, 0), (older, 3)):
        article = issue.languages[lang].articles[0]
        item = items[offset]
        url = f"{ORIGIN}/{lang}/issues/{issue.issue_id}/articles/{article.slug}/"
        assert item.findtext("title") == article.headline
        assert item.findtext("link") == url
        assert item.findtext("guid") == f"replicantpravda:{issue.issue_id}:{lang}:{article.id}"
        assert item.find("guid").get("isPermaLink") == "false"
        assert unescape(item.findtext("description")) == article.body[0].text
        assert "<script>" not in item.findtext("description")
        assert parsedate_to_datetime(item.findtext("pubDate")).date() == issue.publication_date
    assert items[0].findtext("category") == {"ru": "Мнение", "en": "Opinion", "ja": "論説"}[lang]
    changed = latest.model_dump()
    changed["revision"] += 1
    changed["languages"][lang]["articles"][0]["headline"] = "Исправление / correction / 訂正"
    changed["languages"][lang]["articles"][0]["slug"] = "corrected-slug"
    build(Issue.model_validate(changed), tmp_path / "corrected", archive_issues=(older,))
    corrected = ET.parse(tmp_path / "corrected" / lang / "rss.xml").find("channel/item")
    assert corrected.findtext("guid") == items[0].findtext("guid")
    assert corrected.findtext("title") != items[0].findtext("title")
    assert corrected.findtext("link") != items[0].findtext("link")


def test_sitemap_contains_canonical_reader_pages_and_no_aliases(issues, tmp_path):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,))
    root = ET.parse(site / "sitemap.xml").getroot()
    assert root.tag == f"{{{SITEMAP_NS}}}urlset"
    urls = [entry.findtext(f"{{{SITEMAP_NS}}}loc") for entry in root]
    assert (
        len(urls) == len(set(urls)) == 39
    )  # Nine landing/archive/about pages + 2 × 3 × (issue + 4 articles).
    assert not any("/print/" in url or url.endswith(".pdf") for url in urls)
    assert ORIGIN + "/" not in urls
    assert not any(f"/{lang}/articles/" in url for lang in ("ru", "en", "ja") for url in urls)
    assert root.findall(f".//{{{SITEMAP_NS}}}lastmod") == []
    assert verify_site_links(site) == []
    assert verify_snapshot(site, "2026-10-31")["passed"]
    assert "Disallow: /" in (site / "robots.txt").read_text()
    assert f"Sitemap: {ORIGIN}/sitemap.xml" in (site / "robots.txt").read_text()


def test_drafts_and_review_are_absent_from_rss_and_sitemap(tmp_path):
    selected = [
        make_issue("2026-10-31", "draft"),
        make_issue("2026-10-30", "review"),
        make_issue("2026-10-29", "approved"),
        make_issue("2026-10-28", "published"),
    ]
    site = tmp_path / "mixed"
    build(selected[0], site, archive_issues=tuple(selected[1:]))
    for lang in ("ru", "en", "ja"):
        rss = (site / lang / "rss.xml").read_text()
        assert "/issues/2026-10-31/" not in rss and "/issues/2026-10-30/" not in rss
        assert len(ET.fromstring(rss).findall("channel/item")) == 6
    locations = ET.parse(site / "sitemap.xml").findall(f".//{{{SITEMAP_NS}}}loc")
    assert all(
        "/issues/2026-10-29/" in url.text or "/issues/2026-10-28/" in url.text for url in locations
    )
    draft_site = tmp_path / "drafts"
    build(selected[0], draft_site, archive_issues=(selected[1],))
    assert not (draft_site / "sitemap.xml").exists()  # Do not emit an invalid empty urlset.
    for lang in ("ru", "en", "ja"):
        assert not ET.parse(draft_site / lang / "rss.xml").findall("channel/item")
    assert selected[0].status == "draft"
    assert verify_discovery(draft_site, selected[:2]) == []


def test_canonical_and_hreflang_preserve_page_issue_and_article(issues, tmp_path):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,))
    article = older.languages["ru"].articles[0]
    routes = {
        "": "/ru/",
        "ru": "/ru/",
        "ru/archive": "/ru/archive/",
        "ru/issues/2026-10-30": "/ru/issues/2026-10-30/",
        f"ru/issues/2026-10-30/articles/{article.slug}": f"/ru/issues/2026-10-30/articles/{article.slug}/",
        f"ru/articles/{article.slug}": f"/ru/issues/2026-10-31/articles/{article.slug}/",
    }
    for route, canonical in routes.items():
        links = head_links(site, route)
        assert [link["href"] for link in links if link.get("rel") == "canonical"] == [
            ORIGIN + canonical
        ]
        assert len([link for link in links if link.get("hreflang")]) == 3
    links = head_links(site, f"ru/issues/2026-10-30/articles/{article.slug}")
    english = next(link for link in links if link.get("hreflang") == "en")
    assert english["href"] == ORIGIN + "/en/issues/2026-10-30/articles/english-slug/"
    html = (site / "ru/issues/2026-10-30/articles" / article.slug / "index.html").read_text()
    assert f"<title>{escape(article.headline)} ·" in html
    assert 'name="description"' in html
    assert 'name="robots" content="noindex,nofollow"' in html


@pytest.mark.parametrize(
    "url",
    [
        "repravda.com",
        "//repravda.com",
        "ftp://repravda.com",
        "javascript:alert(1)",
        "https://user:secret@repravda.com",
        "https://repravda.com/path",
        "https://repravda.com/?x=1",
        "https://repravda.com/#anchor",
        "https://repravda.com?",
        "https://repravda.com#",
        "https://repravda.com\n",
        "https://repravda.com\\@evil.test",
        "http://localhost:invalid",
    ],
)
def test_reject_unsafe_site_origins(url, tmp_path):
    with pytest.raises(ValueError):
        build(make_issue("2026-10-31", "draft"), tmp_path / "bad", site_url=url)
    assert not (tmp_path / "bad").exists()


def test_cli_origin_override_and_normalization(tmp_path, monkeypatch):
    issue = make_issue("2026-10-31", "approved")
    (tmp_path / "2026-10-31.json").write_text(issue.model_dump_json())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rp",
            "build",
            "--issue",
            "2026-10-31",
            "--content-dir",
            str(tmp_path),
            "--site-url",
            "http://LOCALHOST:8010/",
            "--output",
            str(tmp_path / "site"),
        ],
    )
    assert main() == 0
    origin = json.loads((tmp_path / "site/site.json").read_text())["site_url"]
    assert origin == normalize_site_url("http://LOCALHOST:8010/") == "http://localhost:8010"
    assert f"{origin}/ru/" in (tmp_path / "site/ru/index.html").read_text()
    assert verify_site_links(tmp_path / "site") == []


@pytest.mark.parametrize("target", ["canonical", "hreflang", "rss", "sitemap"])
def test_verification_rejects_inconsistent_metadata(issues, tmp_path, target):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,))
    if target in {"canonical", "hreflang"}:
        path = site / "ru/index.html"
        text = path.read_text()
        text = (
            text.replace('rel="canonical"', 'rel="missing-canonical"')
            if target == "canonical"
            else text.replace('hreflang="en"', 'hreflang="de"', 1)
        )
        path.write_text(text)
    elif target == "rss":
        path = site / "ru/rss.xml"
        path.write_text(
            path.read_text().replace(
                '<guid isPermaLink="false">', '<guid isPermaLink="false">wrong-', 1
            )
        )
    else:
        path = site / "sitemap.xml"
        path.write_text(path.read_text().replace("/ru/archive/", "/ru/articles/noncanonical/", 1))
    assert verify_discovery(site, [latest, older])
