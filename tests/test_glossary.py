"""Article glossaries must use only relevant terms from the same issue."""

from html import unescape
from pathlib import Path

import pytest

from replicantpravda.glossary import article_glossary, glossary_entries, mentions
from replicantpravda.models import Issue
from replicantpravda.render import build, load_issue
from replicantpravda.verification import verify_snapshot


@pytest.mark.parametrize(
    "lang,term,text,expected",
    [
        ("ru", "Синхронизация", "Это называют синхронизацией камер.", True),
        ("ru", "Награда", "Робот учится с промежуточной наградой.", True),
        ("ru", "Обучение с подкреплением", "Для обучения с подкреплением.", True),
        ("ru", "Грузоподъёмность", "Заявлена грузоподъемность робота.", True),
        ("en", "AI", "Said devices failed.", False),
        ("en", "AI", "OpenAI announced a model.", False),
        ("en", "AI", "A new AI-based controller.", True),
        ("en", "Reward", "The policy learns from rewards.", True),
        ("en", "Degree of freedom", "It has 21 degrees of freedom.", True),
        ("en", "Trajectory", "The trajectories are different.", True),
        ("ja", "模倣学習（もほうがくしゅう）", "模倣学習を使う。", True),
        ("ja", "同期（どうき）", "同期（どうき）という。", True),
        ("ja", "AI", "AIを使う。", True),
        ("ja", "AI", "OpenAIが発表した。", False),
        ("ja", "校正（こうせい）", "ロボットが学ぶ。", False),
    ],
)
def test_matching_boundaries_inflections_and_readings(lang, term, text, expected):
    assert mentions(term, text, lang) is expected


@pytest.fixture
def issue():
    data = load_issue(Path("content/issues/2026-10-29.json")).model_dump()
    examples = {
        "ru": ("Синхронизация", "Калибровка", "Камеры работают с синхронизацией."),
        "en": ("AI", "Calibration", "Said instruments use AI."),
        "ja": ("模倣学習（もほうがくしゅう）", "校正（こうせい）", "ロボットは模倣学習を使う。"),
    }
    for lang, edition in data["languages"].items():
        term, other, body = examples[lang]
        news = edition["articles"][0]
        news.update(
            headline="Robotics / ロボット / Роботы",
            dek="",
            body=[{"type": "paragraph", "text": body}],
        )
        news["sources"][0]["title"] = other
        edition["articles"].append(
            {
                "id": "glossary",
                "slug": "glossary",
                "category": "analysis",
                "headline": "Glossary",
                "sources": news["sources"],
                "body": [
                    {"type": "heading", "text": term},
                    {"type": "paragraph", "text": f"Definition mentioning {other}."},
                    {"type": "heading", "text": other},
                    {"type": "paragraph", "text": "Unused definition / 未使用 / Не используется."},
                ],
            }
        )
    return Issue.model_validate(data)


@pytest.mark.parametrize("lang", ["ru", "en", "ja"])
def test_relevant_subset_and_full_issue_dictionary(issue, tmp_path, lang):
    edition = issue.languages[lang]
    entries = glossary_entries(edition)
    assert len(entries) == 2
    assert article_glossary(edition.articles[0], entries, lang) == entries[:1]
    root = tmp_path / "site"
    build(issue, root)
    html = (root / lang / "articles" / edition.articles[0].slug / "index.html").read_text()
    related = unescape(html.split('<aside class="article-glossary">')[1].split("</aside>")[0])
    assert related.count('class="glossary-entry"') == 1
    assert entries[0].term in related
    assert "Unused definition" not in related
    assert f"/{lang}/issues/{issue.issue_id}/#article-glossary" in related
    assert html.index('<aside class="article-glossary">') > html.index("<footer><h3>")
    for route in (f"{lang}/index.html", f"{lang}/articles/glossary/index.html"):
        glossary = unescape((root / route).read_text())
        assert glossary.count('class="glossary-entry"') == 2
        assert all(entry.term in glossary and entry.definition in glossary for entry in entries)
    assert verify_snapshot(root, str(issue.issue_id))["passed"]


def test_no_empty_panel_or_self_append(issue, tmp_path):
    data = issue.model_dump()
    for edition in data["languages"].values():
        edition["articles"][0]["body"][0]["text"] = "Nothing relevant / Ничего / 関係なし"
    modified = Issue.model_validate(data)
    root = tmp_path / "site"
    build(modified, root)
    for lang, edition in modified.languages.items():
        html = (root / lang / "articles" / edition.articles[0].slug / "index.html").read_text()
        assert 'class="article-glossary"' not in html
        assert article_glossary(edition.articles[-1], glossary_entries(edition), lang) == []
        assert (root / lang / "articles/glossary/index.html").read_text().count(
            'class="glossary-panel"'
        ) == 1


def test_explicit_aliases_never_add_terms_outside_issue_dictionary(issue):
    edition = issue.languages["ru"]
    article = edition.articles[0].model_copy(
        update={
            "headline": "Работа камер",
            "body": edition.articles[0].body[:1],
        }
    )
    article.body[0].text = "Камеры снимают одновременно."
    entries = glossary_entries(edition)
    assert article_glossary(article, entries, "ru") == []
    aliases = {"Синхронизация": ["снимают одновременно"], "Несуществующее понятие": ["камеры"]}
    assert article_glossary(article, entries, "ru", aliases) == entries[:1]


def test_html_escaping_and_legacy_unstructured_dictionary(issue, tmp_path):
    data = issue.model_dump()
    glossary = data["languages"]["en"]["articles"][-1]
    glossary["body"][0]["text"] = '<img src=x onerror="alert(1)">'
    glossary["body"][1]["text"] = "<script>bad()</script>"
    data["languages"]["ru"]["articles"][-1]["body"] = [
        {"type": "paragraph", "text": "Legacy dictionary text"}
    ]
    modified = Issue.model_validate(data)
    root = tmp_path / "site"
    build(modified, root)
    html = (root / "en/articles/glossary/index.html").read_text()
    assert "<img src=x" not in html and "<script>bad" not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html
    assert "Legacy dictionary text" in (root / "ru/articles/glossary/index.html").read_text()
    assert "Legacy dictionary text" in (root / "ru/index.html").read_text()
    assert glossary_entries(modified.languages["ru"]) == []
