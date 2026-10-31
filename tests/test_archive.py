"""Historical routes must preserve their issue even when article slugs repeat."""

import json
import os
from datetime import date
from html import escape
from pathlib import Path

import pytest

from replicantpravda.archive import collect_issues
from replicantpravda.cli import main
from replicantpravda.models import Issue
from replicantpravda.render import build, load_issue
from replicantpravda.verification import PageLinks, verify_site_links, verify_snapshot


@pytest.fixture
def issues() -> tuple[Issue, Issue]:
    original = load_issue(Path("content/issues/2026-10-29.json"))
    result = []
    for day, number in (("2026-10-30", 2), ("2026-10-31", 3)):
        data = original.model_dump(mode="json")
        data.update(issue_id=day, publication_date=day, number=number, weather=None)
        for lang, edition in data["languages"].items():
            edition["issue_title"] = f"{lang} <{day}>"
            edition["editorial_note"] = f"{day} & {lang}"
            for article in edition["articles"]:
                article["headline"] += " " + day
        result.append(Issue.model_validate(data))
    return tuple(result)


@pytest.mark.parametrize("lang", ["ru", "en", "ja"])
def test_archive_routes_language_and_repeated_slugs(issues, tmp_path, lang):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,))
    archive = (site / lang / "archive/index.html").read_text()
    assert 'class="archive-list"' in archive
    assert archive.index('datetime="2026-10-31"', archive.index("<main>")) < archive.index(
        'datetime="2026-10-30"'
    )
    assert 'class="edition-articles"' not in archive
    assert "edition.pdf" not in archive  # A web-only snapshot offers no nonexistent PDFs.
    assert escape(older.languages[lang].issue_title) in archive
    assert f'href="/{lang}/archive/"' in archive
    for issue in issues:
        prefix = f"/{lang}/issues/{issue.issue_id}"
        edition = issue.languages[lang]
        article = edition.articles[0]
        html = (site / prefix.lstrip("/") / "index.html").read_text()
        assert f'href="{prefix}/articles/{article.slug}/"' in html
        for code in ("ru", "en", "ja"):
            assert f'href="/{code}/issues/{issue.issue_id}/"' in html
        article_html = (
            site / prefix.lstrip("/") / "articles" / article.slug / "index.html"
        ).read_text()
        assert escape(article.headline) in article_html
        assert f'href="{prefix}/#article-{article.id}"' in article_html
        for code in ("ru", "en", "ja"):
            slug = issue.languages[code].articles[0].slug
            assert f'href="/{code}/issues/{issue.issue_id}/articles/{slug}/"' in article_html
    alias = (
        site / lang / "articles" / latest.languages[lang].articles[0].slug / "index.html"
    ).read_text()
    assert escape(latest.languages[lang].articles[0].headline) in alias
    assert escape(older.languages[lang].articles[0].headline) not in alias
    assert verify_site_links(site) == []
    assert verify_snapshot(site, "2026-10-31")["passed"]


def test_archive_selection_is_explicit_and_deterministic(issues, tmp_path):
    older, latest = issues
    for name in ("first", "repeat"):
        build(latest, tmp_path / name, archive_issues=(older,))
    for path in (tmp_path / "first").rglob("*"):
        if path.is_file():
            assert (
                path.read_bytes()
                == (tmp_path / "repeat" / path.relative_to(tmp_path / "first")).read_bytes()
            )
    build(latest, tmp_path / "alone")
    assert not (tmp_path / "alone/ru/issues/2026-10-30").exists()
    assert 'class="archive-list"' in (tmp_path / "alone/ru/archive/index.html").read_text()
    assert "2026-10-30" not in (tmp_path / "alone/ru/archive/index.html").read_text()
    assert collect_issues(latest, (older,)) == [latest, older]
    with pytest.raises(ValueError, match="Duplicate"):
        build(latest, tmp_path / "duplicate", archive_issues=(latest,))
    with pytest.raises(ValueError, match="newer"):
        build(older, tmp_path / "future", archive_issues=(latest,))
    mismatched = older.model_copy(update={"publication_date": date(2026, 10, 29)})
    with pytest.raises(ValueError, match="must match"):
        build(latest, tmp_path / "mismatch", archive_issues=(mismatched,))
    assert not (tmp_path / "duplicate").exists()
    assert not (tmp_path / "future").exists()


def test_archive_cli(issues, monkeypatch, tmp_path):
    older, latest = issues
    for issue in issues:
        (tmp_path / f"{issue.issue_id}.json").write_text(issue.model_dump_json())
    monkeypatch.setattr(
        "sys.argv",
        [
            "rp",
            "build",
            "--issue",
            "2026-10-31",
            "--content-dir",
            str(tmp_path),
            "--archive-issue",
            str(tmp_path / "2026-10-30.json"),
            "--output",
            str(tmp_path / "site"),
        ],
    )
    assert main() == 0
    index = json.loads((tmp_path / "site/archive.json").read_text())
    assert [entry["issue_id"] for entry in index["issues"]] == ["2026-10-31", "2026-10-30"]
    assert (tmp_path / "site/source.json").read_text() == latest.model_dump_json(indent=2) + "\n"
    assert (tmp_path / "site/sources/2026-10-30.json").read_text() == older.model_dump_json(
        indent=2
    ) + "\n"


def test_missing_historical_illustration_aborts_snapshot(issues, tmp_path):
    older, latest = issues
    data = older.model_dump()
    path = "data/images/2026-10-30/missing.webp"
    for edition in data["languages"].values():
        edition["articles"][0]["image"] = {
            "path": path,
            "url": "https://raw.githubusercontent.com/vanderlvoff/pravdareplikanta/main/" + path,
            "type": "generated",
            "alt": "Missing test image",
            "caption": "Missing test image",
        }
    with pytest.raises(ValueError, match="Missing or unsafe"):
        build(latest, tmp_path / "failed", archive_issues=(Issue.model_validate(data),))
    assert not (tmp_path / "failed").exists()


def test_link_verifier_detects_missing_archived_page_and_fragment(issues, tmp_path):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,))
    page = site / "ru/issues/2026-10-30/index.html"
    page.write_text(page.read_text().replace('id="article-robot-evaluation"', 'id="removed"'))
    assert any("missing fragment" in error for error in verify_site_links(site))
    page.unlink()
    assert any("missing local target" in error for error in verify_site_links(site))


@pytest.mark.skipif(os.environ.get("RP_TEST_PDF") != "1", reason="Set RP_TEST_PDF=1 for Chromium")
def test_historical_pdfs_are_independent(issues, tmp_path):
    older, latest = issues
    site = tmp_path / "site"
    build(latest, site, archive_issues=(older,), pdf=True)
    report = verify_snapshot(site, str(latest.issue_id))
    assert report["passed"]
    assert set(report["archive"]) == {"2026-10-30", "2026-10-31"}
    for lang in ("ru", "en", "ja"):
        links = PageLinks((site / lang / "archive/index.html").read_text()).hrefs
        for issue in issues:
            assert f"/{lang}/issues/{issue.issue_id}/edition.pdf" in links
            assert report["archive"][str(issue.issue_id)][lang]["page_count"] >= 1
        assert (site / lang / "print/index.html").read_bytes() == (
            site / lang / "issues/2026-10-31/print/index.html"
        ).read_bytes()
