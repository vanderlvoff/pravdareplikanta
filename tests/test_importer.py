"""Validate daily feed normalization, source integrity and offline CLI import."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from replicantpravda.cli import main
from replicantpravda.importer import import_feed, save_import
from replicantpravda.render import build, load_issue


@pytest.fixture
def feed_folder(tmp_path):
    folder = tmp_path / "feed"
    folder.mkdir()
    # Use the owner's archived fixture, independent of the rolling latest folder.
    archived = Path("data/archive/2026/10/30")
    for lang in ("ru", "en", "ja"):
        data = json.loads((archived / f"{lang}.json").read_text())
        for item in data["news"]:
            item["body"] = {
                "ru": "Редакционный текст статьи.\n\nВторой абзац: робот работает.",
                "en": "Edited article text.\n\nSecond paragraph: the robot works.",
                "ja": "編集済みの記事本文。\n\n第二段落：ロボットが働く。",
            }[lang]
        (folder / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False))
    return folder


@pytest.fixture
def template():
    return load_issue(Path("content/issues/2026-10-30.json"))


def test_import_preserves_sections_and_sources(feed_folder, template, tmp_path):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in feed_folder.iterdir()}
    issue, report = import_feed(feed_folder, template, number=2, revision=2)
    assert issue.status == "draft" and issue.revision == 2
    assert issue.weather == template.weather
    for lang in ("ru", "en", "ja"):
        raw = json.loads((feed_folder / f"{lang}.json").read_text())
        edition = issue.languages[lang]
        assert edition.title == template.languages[lang].title
        assert edition.issue_title == raw["title"]
        assert edition.editorial_note == raw["lead"]
        by_id = {a.id: a for a in edition.articles}
        for item in raw["news"]:
            article = by_id[item["id"]]
            assert article.headline == item["title"]
            assert article.dek == ""
            assert [block.text for block in article.body] == item["body"].split("\n\n")
            expected = {s["url"] for s in raw["sources"] if s["id"] in item["source_ids"]}
            assert {str(s.url) for s in article.sources} == expected
        glossary = by_id["glossary"]
        assert [block.text for block in glossary.body] == [
            text for item in raw["glossary"] for text in (item["term"], item["definition"])
        ]
        assert by_id["technology-signal"].headline == raw["technology_signal"]["title"]
        assert by_id["technology-signal"].body[0].text == raw["technology_signal"]["implications"]
        assert report["sources"][lang]["sha256"] == before[f"{lang}.json"]
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in feed_folder.iterdir()
    }
    build(issue, tmp_path / "site")
    html = (tmp_path / "site/ru/index.html").read_text()
    assert issue.languages["ru"].issue_title in html
    assert "glossary" in html


def test_jp_alias(feed_folder, template):
    (feed_folder / "ja.json").rename(feed_folder / "jp.json")
    path = feed_folder / "jp.json"
    data = json.loads(path.read_text())
    data["language"] = "jp"
    path.write_text(json.dumps(data))
    issue, report = import_feed(feed_folder, template, number=2, revision=2)
    assert "ja" in issue.languages
    assert report["sources"]["ja"]["file"].endswith("jp.json")


@pytest.mark.parametrize(
    "fault",
    [
        "reference",
        "url",
        "domain",
        "date",
        "language",
        "unknown_field",
        "duplicate",
        "source_mismatch",
        "news_mismatch",
        "both_ja_jp",
        "missing_body",
        "empty_body",
        "empty_body_list",
    ],
)
def test_invalid_import_does_not_create_output(feed_folder, template, tmp_path, fault):
    path = feed_folder / "en.json"
    data = json.loads(path.read_text())
    if fault == "reference":
        data["news"][0]["source_ids"] = ["missing"]
    elif fault == "url":
        data["sources"][0]["url"] = "javascript:alert(1)"
    elif fault == "domain":
        data["sources"][0]["domain"] = "different.example"
    elif fault == "date":
        data["issue_date"] = "2026-10-31"
        data["issue_id"] = "daily-2026-10-31"
    elif fault == "language":
        data["language"] = "ru"
    elif fault == "unknown_field":
        data["unmapped_section"] = "Do not silently discard this"
    elif fault == "duplicate":
        data["news"].append(copy.deepcopy(data["news"][0]))
    elif fault == "source_mismatch":
        data["sources"][0]["url"] = "https://www.agibot.com/different"
    elif fault == "news_mismatch":
        data["news"].pop()
    elif fault == "missing_body":
        del data["news"][0]["body"]
    elif fault == "empty_body":
        data["news"][0]["body"] = "  "
    elif fault == "empty_body_list":
        data["news"][0]["body"] = []
    else:
        (feed_folder / "jp.json").write_bytes((feed_folder / "ja.json").read_bytes())
    path.write_text(json.dumps(data))
    output = tmp_path / "imported.json"
    with pytest.raises(ValueError):
        save_import(feed_folder, template, output, number=2, revision=2)
    assert not output.exists()
    assert not output.with_suffix(".import.json").exists()


def test_import_cli_and_no_overwrite(feed_folder, monkeypatch, tmp_path):
    output = tmp_path / "imported.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "rp",
            "import",
            "--input",
            str(feed_folder),
            "--template",
            "content/issues/2026-10-30.json",
            "--number",
            "2",
            "--revision",
            "2",
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    before = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    "body", ["Первый абзац.\nВторой абзац.", ["Первый абзац.", "Второй абзац."]]
)
def test_reader_body_replaces_editorial_fields(feed_folder, template, tmp_path, body):
    path = feed_folder / "ru.json"
    raw = json.loads(path.read_text())
    item = raw["news"][0]
    item["body"] = body
    hidden = (
        "summary",
        "details",
        "technical_novelty",
        "engineering_impact",
        "limitations",
        "evidence_status",
    )
    for key in hidden:
        item[key] = f"HIDDEN_EDITORIAL_{key}"
    # These metadata fields may also be omitted altogether.
    for key in hidden:
        raw["news"][1].pop(key)
    path.write_text(json.dumps(raw, ensure_ascii=False))
    issue, _ = import_feed(feed_folder, template, number=2, revision=3)
    article = issue.languages["ru"].articles[0]
    assert [block.text for block in article.body] == ["Первый абзац.", "Второй абзац."]
    build(issue, tmp_path / "site")
    for relative in (
        "ru/index.html",
        f"ru/articles/{article.slug}/index.html",
    ):
        html = (tmp_path / "site" / relative).read_text()
        assert "Первый абзац." in html
        assert "HIDDEN_EDITORIAL_" not in html
        if relative != "ru/index.html":
            assert "Второй абзац." in html


def test_body_html_is_escaped(feed_folder, template, tmp_path):
    path = feed_folder / "ru.json"
    raw = json.loads(path.read_text())
    raw["news"][0]["body"] = '<script>alert("test")</script>'
    path.write_text(json.dumps(raw))
    issue, _ = import_feed(feed_folder, template, number=2, revision=3)
    build(issue, tmp_path / "site")
    article = issue.languages["ru"].articles[0]
    html = (tmp_path / "site" / f"ru/articles/{article.slug}/index.html").read_text()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_archived_v12_editorial_body(template):
    folder = Path("data/archive/2026/10/30/revisions/v1.2-0146")
    issue, report = import_feed(folder, template, number=2, revision=3)
    for lang in ("ru", "en", "ja"):
        raw = json.loads((folder / f"{lang}.json").read_text())
        by_id = {article.id: article for article in issue.languages[lang].articles}
        assert len(raw["news"]) == 8
        for item in raw["news"]:
            article = by_id[item["id"]]
            assert article.headline == item["title"] and article.dek == ""
            assert "\n\n".join(block.text for block in article.body) == item["body"]
    assert report["pagination"] == "automatic"
