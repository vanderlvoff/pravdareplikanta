"""Repository image security, multilingual feed mapping, and figure layout coverage."""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from replicantpravda.illustrations import webp_dimensions
from replicantpravda.importer import import_feed
from replicantpravda.models import ArticleImage
from replicantpravda.render import build, load_issue
from replicantpravda.verification import verify_snapshot

FIXTURE = Path("tests/fixtures/editorial-illustration.webp")


@pytest.fixture
def illustrated_feed(tmp_path):
    folder = tmp_path / "feed"
    folder.mkdir()
    for lang in ("ru", "en", "ja"):
        raw = json.loads(
            Path(f"data/archive/2026/10/30/revisions/v1.2-0146/{lang}.json").read_text()
        )
        raw["schema_version"] = "1.3"
        for index, item in enumerate(raw["news"]):
            relative = f"data/images/2026-10-30/test-{index}.webp"
            item["image"] = (
                {
                    "url": "https://raw.githubusercontent.com/vanderlvoff/pravdareplikanta/main/"
                    + relative,
                    "path": relative,
                    "type": "generated",
                    "caption": {
                        "ru": "Тестовая иллюстрация",
                        "en": "Test illustration",
                        "ja": "テスト用イラスト",
                    }[lang],
                    "alt": {"ru": "Тестовая схема", "en": "Test diagram", "ja": "テスト用の図"}[
                        lang
                    ],
                }
                if index < 2
                else None
            )
            if item["image"]:
                destination = tmp_path / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(FIXTURE.read_bytes())
        (folder / f"{lang}.json").write_text(json.dumps(raw, ensure_ascii=False))
    issue, report = import_feed(
        folder, load_issue(Path("content/localized/2026-10-30.json")), number=2, revision=5
    )
    return tmp_path, folder, issue


def test_illustrated_feed_and_offline_build(illustrated_feed, tmp_path, monkeypatch):
    root, _, issue = illustrated_feed

    def no_network(*args, **kwargs):
        raise AssertionError("Build must not fetch images")

    monkeypatch.setattr("replicantpravda.weather.urlopen", no_network)
    build(issue, tmp_path / "site", image_root=root)
    for lang in ("ru", "en", "ja"):
        articles = [a for a in issue.languages[lang].articles if a.image]
        assert len(articles) == 2
        html = (tmp_path / "site" / lang / "index.html").read_text()
        assert html.count('class="article-illustration"') == 2
        for article in articles:
            assert article.image.caption in html and article.image.alt in html
            assert f'src="/{article.image.path}"' in html
            assert 'width="240" height="150"' in html
            assert (tmp_path / "site" / article.image.path).read_bytes() == FIXTURE.read_bytes()
            detail = (
                tmp_path / "site" / lang / "articles" / article.slug / "index.html"
            ).read_text()
            assert article.image.caption in detail


@pytest.mark.parametrize("fault", ["count", "missing_field", "language_image"])
def test_v13_image_contract(illustrated_feed, fault):
    root, folder, _ = illustrated_feed
    path = folder / "en.json"
    raw = json.loads(path.read_text())
    if fault == "count":
        raw["news"][0]["image"] = None
    elif fault == "missing_field":
        del raw["news"][2]["image"]
    else:
        image = raw["news"][0]["image"]
        image["path"] = image["path"].replace("test-0", "different")
        image["url"] = image["url"].replace("test-0", "different")
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        import_feed(
            folder, load_issue(Path("content/localized/2026-10-30.json")), number=2, revision=5
        )


@pytest.mark.parametrize("fault", ["traversal", "remote_url", "mismatched_url"])
def test_unsafe_image_references(illustrated_feed, fault):
    image = illustrated_feed[2].languages["ru"].articles[0].image.model_dump()
    if fault == "traversal":
        image["path"] = "data/images/../../secret.webp"
    elif fault == "remote_url":
        image["url"] = "https://untrusted.example/image.webp"
    else:
        image["url"] = str(image["url"]).replace("test-0", "wrong")
    with pytest.raises(ValidationError):
        ArticleImage.model_validate(image)


@pytest.mark.parametrize("fault", ["missing", "corrupt", "symlink"])
def test_invalid_local_image_leaves_no_build(illustrated_feed, tmp_path, fault):
    root, _, issue = illustrated_feed
    image = root / issue.languages["ru"].articles[0].image.path
    image.unlink()
    if fault == "corrupt":
        image.write_bytes(b"not an image")
    elif fault == "symlink":
        outside = root / "outside.webp"
        outside.write_bytes(FIXTURE.read_bytes())
        image.symlink_to(outside)
    with pytest.raises(ValueError):
        build(issue, tmp_path / "invalid", image_root=root)
    assert not (tmp_path / "invalid").exists()


def test_webp_dimensions_and_truncation():
    assert webp_dimensions(FIXTURE.read_bytes()) == (240, 150)
    with pytest.raises(ValueError):
        webp_dimensions(FIXTURE.read_bytes()[:30])


@pytest.mark.skipif(os.environ.get("RP_TEST_PDF") != "1", reason="Set RP_TEST_PDF=1 for Chromium")
def test_illustrated_pdf_pagination(illustrated_feed, tmp_path):
    root, _, issue = illustrated_feed
    build(issue, tmp_path / "pdf", image_root=root, pdf=True)
    assert verify_snapshot(tmp_path / "pdf", str(issue.issue_id))["passed"]
    for lang in ("ru", "en", "ja"):
        layout = json.loads(
            (
                tmp_path / "pdf" / lang / "issues" / str(issue.issue_id) / "pagination.json"
            ).read_text()
        )
        assert len(layout["images"]) == 2
