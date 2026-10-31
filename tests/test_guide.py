"""The newspaper story/help page keeps language and audience navigation intact."""

import json
from html import escape
from pathlib import Path

import pytest

from replicantpravda.readers import READER_EDITIONS, reader_base
from replicantpravda.render import build, load_issue
from replicantpravda.verification import PageLinks, verify_snapshot


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    issues = [
        load_issue(Path("content/issues/2026-10-29.json")).model_copy(update={"edition": code})
        for code in READER_EDITIONS
    ]
    root = tmp_path_factory.mktemp("guide") / "site"
    build(issues[0], root, reader_issues=tuple(issues[1:]))
    return root


@pytest.mark.parametrize("code", READER_EDITIONS)
@pytest.mark.parametrize("lang", ["ru", "en", "ja"])
def test_guide_content_language_and_audience_routes(site, code, lang):
    base = reader_base(lang, code)
    labels = json.loads(Path("src/replicantpravda/templates/guide.json").read_text())[lang]
    html = (site / base.lstrip("/") / "about/index.html").read_text()
    assert escape(labels["title"]) in html
    assert escape(labels["intro"]) in html
    assert escape(labels["mail_status"]) in html
    assert all(escape(text) in html for text in labels["editions"].values())
    assert 'class="guide-page"' in html
    assert 'class="guide-status"' in html
    assert "<form" not in html  # No pretend subscription or printer setup.
    assert "edition.pdf" not in html  # This fixture is web-only.
    assert f'data-reader-edition="{code}"' in html
    links = PageLinks(html)
    for language in ("ru", "en", "ja"):
        assert reader_base(language, code) + "about/" in links.hrefs
    for edition in READER_EDITIONS:
        assert reader_base(lang, edition) + "about/" in links.hrefs
        assert reader_base(lang, edition) in links.hrefs
    assert base + "about/" in PageLinks((site / base.lstrip("/") / "index.html").read_text()).hrefs
    assert verify_snapshot(site, "2026-10-29")["passed"]


def test_unavailable_editions_are_not_linked_from_guide(tmp_path):
    root = tmp_path / "site"
    build(load_issue(Path("content/issues/2026-10-29.json")), root)
    html = (root / "ru/about/index.html").read_text()
    assert "Скоро" in html
    links = PageLinks(html)
    assert not any(
        "/children/" in path or "/business/" in path or "/enthusiast/" in path
        for path in links.hrefs
    )
    assert not (root / "ru/children/about").exists()
