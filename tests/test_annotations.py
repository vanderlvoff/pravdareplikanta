"""Footnote offsets, accessible round trips and preserved source text."""

from html.parser import HTMLParser
from pathlib import Path

import pytest

from replicantpravda.annotations import annotate_article, mention_span
from replicantpravda.glossary import GlossaryEntry
from replicantpravda.render import load_issue


class TextWithoutNotes(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.parts = []
        self.hidden = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "sup":
            self.hidden = True

    def handle_endtag(self, tag):
        if tag == "sup":
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


@pytest.mark.parametrize(
    "lang,term,text,expected",
    [
        ("ru", "Синхронизация", "Это называют синхронизацией камер.", "синхронизацией"),
        ("ru", "Грузоподъёмность", "Грузоподъемность выросла.", "Грузоподъемность"),
        ("en", "AI", "Said instruments are made by OpenAI.", None),
        ("en", "Reward", "It learns from rewards.", "rewards"),
        (
            "ja",
            "音声合成（おんせいごうせい）",
            "音声合成（おんせいごうせい）を使う。",
            "音声合成（おんせいごうせい）",
        ),
        ("ja", "模倣学習（もほうがくしゅう）", "模倣学習を使う。", "模倣学習"),
        ("ja", "AI", "ＡＩを使う。", "ＡＩ"),
        ("ja", "ガイド", "ｶﾞｲﾄﾞを読む。", "ｶﾞｲﾄﾞ"),
    ],
)
def test_original_offsets(lang, term, text, expected):
    span = mention_span(term, text, lang)
    assert (text[span[0] : span[1]] if span else None) == expected


def test_order_once_only_overlaps_and_escaping():
    article = (
        load_issue(Path("content/issues/2026-10-29.json"))
        .languages["en"]
        .articles[0]
        .model_copy(deep=True)
    )
    article.headline = "A controller"
    article.dek = ""
    article.body[0].text = "AI model, then calibration. AI again. <script>unsafe()</script>"
    article.body = article.body[:1]
    before = article.model_dump_json()
    entries = [
        GlossaryEntry("Calibration", "Check measurements."),
        GlossaryEntry("AI model", "A model."),
        GlossaryEntry("AI", "A program."),
    ]
    result = annotate_article(article, entries, "en", {}, "Definition")
    assert [note.term for note in result["article_glossary"]] == ["AI", "AI model", "Calibration"]
    html = str(result["annotated_body"][0])
    assert html.index("[1]") < html.index("[2]") < html.index("[3]")
    for number in (1, 2, 3):
        assert html.count(f'id="term-ref-{number}"') == 1
        assert f'href="#term-{number}"' in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "".join(TextWithoutNotes(html).parts) == article.body[0].text
    assert article.model_dump_json() == before


def test_alias_and_list_offsets_use_real_text():
    article = (
        load_issue(Path("content/issues/2026-10-29.json"))
        .languages["ru"]
        .articles[0]
        .model_copy(deep=True)
    )
    from replicantpravda.models import Article

    data = article.model_dump()
    data.update(
        headline="Камеры",
        dek="",
        body=[{"type": "list", "items": ["Камеры снимают одновременно.", "Без повторов."]}],
    )
    article = Article.model_validate(data)
    result = annotate_article(
        article,
        [GlossaryEntry("Синхронизация", "Общий момент.")],
        "ru",
        {"Синхронизация": ["снимают одновременно"]},
        "Определение",
    )
    assert len(result["article_glossary"]) == 1
    assert "одновременно.<" not in str(result["annotated_body"][0][0])
    assert "одновременно<sup" in str(result["annotated_body"][0][0])
    assert str(result["annotated_body"][0][1]) == "Без повторов."
