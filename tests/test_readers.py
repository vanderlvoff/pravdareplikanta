"""Audience identity, valid-feed availability and all twelve localized routes."""

import copy
import json
import os
import shutil
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from replicantpravda.cli import main
from replicantpravda.discovery import article_guid
from replicantpravda.importer import FeedEdition, import_feed
from replicantpravda.models import Issue
from replicantpravda.reader_import import import_readers
from replicantpravda.readers import READER_EDITIONS, reader_base
from replicantpravda.render import build, load_issue
from replicantpravda.verification import PageLinks, verify_snapshot

# Fixed input revision: the date's primary archive is refreshed with each edition.
FEEDS = Path("data/archive/2026/10/31/revisions/before-0.2-refresh-20261031T132532Z")
TEMPLATE = Path("content/technical/2026-10-31.json")


class ReaderText(HTMLParser):
    """Check source wording independently of inserted footnote numbers."""

    def __init__(self, html):
        super().__init__()
        self.parts = []
        self.reference = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "sup" and dict(attrs).get("class") == "term-reference":
            self.reference = True

    def handle_endtag(self, tag):
        if tag == "sup":
            self.reference = False

    def handle_data(self, data):
        if not self.reference:
            self.parts.append(data)


@pytest.fixture(scope="module")
def issues():
    return tuple(
        import_feed(FEEDS / code, load_issue(TEMPLATE), number=3, revision=1)[0]
        for code in READER_EDITIONS
    )


@pytest.fixture(scope="module")
def site(issues, tmp_path_factory):
    root = tmp_path_factory.mktemp("readers") / "site"
    build(
        issues[0],
        root,
        reader_issues=issues[1:],
        archive_issues=(load_issue(Path("content/technical/2026-10-30.json")),),
    )
    return root


@pytest.mark.parametrize("code", READER_EDITIONS)
@pytest.mark.parametrize("lang", ["ru", "en", "ja"])
def test_all_routes_keep_audience_and_language(issues, site, code, lang):
    issue = next(issue for issue in issues if issue.edition == code)
    base = reader_base(lang, code)
    article = issue.languages[lang].articles[0]
    routes = (
        (base, "home"),
        (base + "archive/", "archive"),
        (base + "issues/2026-10-31/", "issue"),
        (base + f"issues/2026-10-31/articles/{article.slug}/", "article"),
    )
    for route, kind in routes:
        html = (site / route.lstrip("/") / "index.html").read_text()
        assert f'data-reader-edition="{code}"' in html
        assert 'class="reader-picker"' in html
        assert 'class="reader-unavailable"' not in html
        page = PageLinks(html)
        assert base in page.hrefs  # Masthead returns to this audience's home.
        assert base + "archive/" in page.hrefs
        for other_lang in ("ru", "en", "ja"):
            target = reader_base(other_lang, code)
            if kind == "archive":
                target += "archive/"
            elif kind in {"issue", "article"}:
                target += "issues/2026-10-31/"
                if kind == "article":
                    slug = next(
                        a.slug for a in issue.languages[other_lang].articles if a.id == article.id
                    )
                    target += f"articles/{slug}/"
            assert target in page.hrefs
        assert 'class="article-illustration"' not in html
        assert "edition.pdf" not in html
    full = (site / routes[-1][0].lstrip("/") / "index.html").read_text()
    text = "".join(ReaderText(full).parts)
    for paragraph in article.body:
        assert paragraph.text in text
    assert base + f"issues/2026-10-31/#article-{article.id}" in full
    # Root/legacy bookmarks remain engineering, including the illustrated archive.
    assert (site / "index.html").read_bytes() == (site / "ru/index.html").read_bytes()


def test_switcher_preserves_matching_article_and_falls_back_to_real_issue(site):
    html = (site / "ru/children/issues/2026-10-31/articles/dexsafe-hand/index.html").read_text()
    assert 'href="/ru/issues/2026-10-31/articles/dexsafe-hand/"' in html
    assert (
        'href="/ru/children/issues/2026-10-31/articles/dexsafe-hand/" aria-current="page"' in html
    )
    # Engineer has no docomo story; link to its same-day issue instead of a missing article.
    html = (site / "ru/children/issues/2026-10-31/articles/docomo-gateway/index.html").read_text()
    assert 'data-edition="engineer" href="/ru/issues/2026-10-31/"' in html
    # Other audiences have no October 30 issue; a real homepage remains available.
    html = (site / "ru/issues/2026-10-30/index.html").read_text()
    assert 'data-edition="children" href="/ru/children/"' in html


def test_historical_images_and_new_null_images(site):
    old = (site / "ru/issues/2026-10-30/index.html").read_text()
    assert old.count('class="article-illustration"') == 2
    assert "vla-stem.webp" in old and "tokio-robot-insurance.webp" in old
    assert (site / "data/images/2026-10-30/vla-stem.webp").is_file()
    archive = (site / "ru/archive/index.html").read_text()
    assert "/ru/issues/2026-10-30/" in archive
    kids_archive = (site / "ru/children/archive/index.html").read_text()
    assert "/ru/children/issues/2026-10-30/" not in kids_archive
    assert (
        "Откуда мы это знаем" in (site / "ru/children/articles/dexsafe-hand/index.html").read_text()
    )


def test_ja_readings_remain_plain_text_and_html_is_escaped(issues, tmp_path):
    data = issues[-1].model_dump()
    reading = "模倣学習（もほうがくしゅう）"
    data["languages"]["ja"]["articles"][0]["body"][0]["text"] += reading + "<ruby>unsafe</ruby>"
    issue = Issue.model_validate(data)
    root = tmp_path / "site"
    build(issue, root)
    article = issue.languages["ja"].articles[0]
    html = (root / f"ja/children/articles/{article.slug}/index.html").read_text()
    assert reading in html and "学習（がくしゅう）" in html
    assert "<ruby>" not in html and "&lt;ruby&gt;" in html
    glossary = (root / "ja/children/articles/glossary/index.html").read_text()
    assert "ことばの説明" in glossary and "編集データに含まれる" not in glossary
    assert verify_snapshot(root, str(issue.issue_id))["passed"]


def test_v14_localized_glossaries_preserve_different_counts(tmp_path):
    folder = tmp_path / "children"
    shutil.copytree(FEEDS / "children", folder)
    expected = {}
    for lang, count in (("ru", 1), ("en", 2), ("ja", 3)):
        path = folder / f"{lang}.json"
        data = json.loads(path.read_text())
        data["glossary"] = data["glossary"][:count]
        if lang == "ja":
            data["glossary"][0]["term"] = "模倣学習（もほうがくしゅう）"
        expected[lang] = [
            value for entry in data["glossary"] for value in (entry["term"], entry["definition"])
        ]
        path.write_text(json.dumps(data, ensure_ascii=False))
    issue, _ = import_feed(folder, load_issue(TEMPLATE), number=3, revision=1)
    for lang, values in expected.items():
        glossary = next(a for a in issue.languages[lang].articles if a.id == "glossary")
        assert [paragraph.text for paragraph in glossary.body] == values
    path = folder / "ja.json"
    data = json.loads(path.read_text())
    data["glossary"] = []
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        import_feed(folder, load_issue(TEMPLATE), number=3, revision=1)


def test_discovery_covers_all_editions_without_guid_collisions(issues, site):
    guids = []
    for issue in issues:
        for lang in ("ru", "en", "ja"):
            rss = ET.parse(site / (reader_base(lang, issue.edition).lstrip("/") + "rss.xml"))
            guids.extend(i.findtext("guid") for i in rss.findall("channel/item"))
            article = issue.languages[lang].articles[0]
            if issue.edition == "engineer":
                assert (
                    article_guid(issue, lang, article)
                    == f"replicantpravda:2026-10-31:{lang}:{article.id}"
                )
    assert len(guids) == len(set(guids))
    assert verify_snapshot(site, "2026-10-31")["passed"]


def test_invalid_or_missing_edition_is_disabled_without_empty_pages(tmp_path):
    folder = tmp_path / "latest"
    shutil.copytree(FEEDS / "engineer", folder / "engineer")
    shutil.copytree(FEEDS / "children", folder / "children")
    path = folder / "children/ja.json"
    raw = json.loads(path.read_text())
    raw["news"][0]["body"] = "Invalid single paragraph"
    path.write_text(json.dumps(raw))
    issues, report = import_readers(folder, load_issue(TEMPLATE), number=3)
    assert set(report["unavailable"]) == {"children", "business", "enthusiast"}
    assert any(i["status"] == "invalid" for i in report["inputs"])
    site = tmp_path / "site"
    build(issues[0], site, import_report=report)
    html = (site / "ru/index.html").read_text()
    assert 'data-edition="children" aria-disabled="true"' in html
    assert "Скоро" in html and 'href="/ru/children/' not in html
    assert not (site / "ru/children").exists()
    assert verify_snapshot(site, "2026-10-31")["passed"]
    with pytest.raises(ValueError, match="No valid"):
        import_readers(tmp_path / "absent", load_issue(TEMPLATE), number=3)


def test_valid_historical_edition_remains_available_without_latest(tmp_path):
    latest = tmp_path / "latest"
    shutil.copytree(FEEDS / "engineer", latest / "engineer")
    archive = tmp_path / "archive/2026/10/30"
    shutil.copytree(FEEDS / "children", archive / "children")
    for path in (archive / "children").glob("*.json"):
        data = json.loads(path.read_text())
        data.update(issue_date="2026-10-30", issue_id="daily-2026-10-30")
        path.write_text(json.dumps(data, ensure_ascii=False))
    issues, report = import_readers(
        latest,
        load_issue(TEMPLATE),
        number=3,
        archives=(archive,),
        legacy_issues=(load_issue(Path("content/technical/2026-10-30.json")),),
    )
    assert "children" not in report["unavailable"]
    root = tmp_path / "site"
    build(
        issues[0],
        root,
        archive_issues=tuple(i for i in issues[1:] if i.edition == "engineer"),
        reader_issues=tuple(i for i in issues if i.edition != "engineer"),
    )
    assert 'data-edition="children" href="/ru/children/"' in (root / "ru/index.html").read_text()
    html = (root / "ja/children/index.html").read_text()
    assert 'datetime="2026-10-30"' in html
    assert not (root / "ja/children/issues/2026-10-31").exists()
    assert verify_snapshot(root, "2026-10-31")["passed"]


@pytest.mark.parametrize(
    "fault", ["edition", "image", "body", "metadata", "null_metadata", "language", "http", "date"]
)
def test_v14_schema_constraints(fault):
    data = json.loads((FEEDS / "children/ja.json").read_text())
    if fault == "edition":
        del data["edition"]
    elif fault == "image":
        del data["news"][0]["image"]
    elif fault == "body":
        data["news"][0]["body"] = ["First", "Second"]
    elif fault == "metadata":
        del data["news"][0]["technical_novelty"]
    elif fault == "null_metadata":
        data["news"][0]["limitations"] = ""
    elif fault == "language":
        data["language"] = "jp"
    elif fault == "http":
        data["sources"][0]["url"] = data["sources"][0]["url"].replace("https:", "http:")
    else:
        data["issue_id"] = "daily-2026-10-30"
    with pytest.raises(ValueError):
        FeedEdition.model_validate(data)


def test_schema_mapping_and_cross_language_audience_mismatch(tmp_path):
    schema = json.loads(Path("data/schema/issue-v1.4.schema.json").read_text())
    assert schema["properties"]["edition"]["enum"] == list(READER_EDITIONS)
    for code in READER_EDITIONS:
        for lang in ("ru", "en", "ja"):
            data = json.loads((FEEDS / code / f"{lang}.json").read_text())
            assert set(data) == set(schema["required"])
            assert set(data["news"][0]) == set(schema["$defs"]["news"]["required"])
            assert all(n["image"] is None for n in data["news"])
            assert FeedEdition.model_validate(data).edition == code
    folder = tmp_path / "children"
    shutil.copytree(FEEDS / "children", folder)
    path = folder / "en.json"
    data = json.loads(path.read_text())
    data["edition"] = "business"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Reader editions"):
        import_feed(folder, load_issue(TEMPLATE), number=3, revision=1)


def test_reader_cli_archived_inputs_and_legacy_isolation(tmp_path, monkeypatch):
    output = tmp_path / "site"
    archive = tmp_path / "archive/2026/10/31"
    shutil.copytree(FEEDS, archive)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rp",
            "build-readers",
            "--input",
            str(tmp_path / "missing"),
            "--template",
            str(TEMPLATE),
            "--number",
            "3",
            "--archive-input",
            str(archive),
            "--legacy-issue",
            str(TEMPLATE),
            "--legacy-issue",
            "content/technical/2026-10-30.json",
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    assert (output / "ja/children/index.html").is_file()
    assert verify_snapshot(output, "2026-10-31")["passed"]
    assert json.loads((output / "verification.json").read_text())["publication"] == "DISABLED"
    assert (output / "reader-import.json").is_file()


def test_no_duplicate_audience_dates_or_cross_audience_history(issues, tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        build(issues[0], tmp_path / "bad", reader_issues=(issues[0],))
    with pytest.raises(ValueError, match="same reader edition"):
        build(issues[0], tmp_path / "bad", archive_issues=(issues[1],))
    build(issues[0], tmp_path / "public", reader_issues=issues[1:], publication=True)
    assert "Allow: /" in (tmp_path / "public/robots.txt").read_text()
    for code in READER_EDITIONS:
        html = (
            tmp_path / "public" / reader_base("ru", code).lstrip("/") / "index.html"
        ).read_text()
        assert 'content="noindex,nofollow"' not in html
    with pytest.raises(ValueError, match="approved/published"):
        build(
            issues[0],
            tmp_path / "bad",
            reader_issues=(issues[-1].model_copy(update={"status": "draft"}),),
            publication=True,
        )


def test_translated_article_slugs_are_used_for_audience_switches(issues, tmp_path):
    selected = copy.deepcopy(issues)
    selected[0].languages["en"].articles[1].slug = "english-engineer-story"
    selected[-1].languages["en"].articles[0].slug = "english-kids-story"
    root = tmp_path / "site"
    build(selected[0], root, reader_issues=selected[1:])
    html = (root / "en/children/articles/english-kids-story/index.html").read_text()
    assert (
        'data-edition="engineer" href="/en/issues/2026-10-31/articles/english-engineer-story/"'
        in html
    )
    assert 'href="/ja/children/issues/2026-10-31/articles/dexsafe-hand/"' in html


@pytest.mark.skipif(os.environ.get("RP_TEST_PDF") != "1", reason="Set RP_TEST_PDF=1 for Chromium")
def test_all_reader_pdfs_and_download_links(issues, tmp_path):
    root = tmp_path / "site"
    build(issues[0], root, reader_issues=issues[1:], pdf=True)
    report = verify_snapshot(root, "2026-10-31")
    assert report["passed"]
    assert len(report["archive"]) == 4
    for issue in issues:
        for lang in ("ru", "en", "ja"):
            base = reader_base(lang, issue.edition)
            pdf_url = f"{base}issues/2026-10-31/edition.pdf"
            pagination = json.loads(
                (root / base.lstrip("/") / "issues/2026-10-31/pagination.json").read_text()
            )
            from replicantpravda.glossary import glossary_entries

            assert len(pagination["glossary_cards"]) == len(glossary_entries(issue.languages[lang]))
            assert (root / pdf_url.lstrip("/")).read_bytes().startswith(b"%PDF-")
            for relative in (base, base + "archive/", base + "issues/2026-10-31/"):
                html = (root / relative.lstrip("/") / "index.html").read_text()
                assert pdf_url in PageLinks(html).hrefs
            assert (root / base.lstrip("/") / "print/index.html").read_bytes() == (
                root / base.lstrip("/") / "issues/2026-10-31/print/index.html"
            ).read_bytes()
