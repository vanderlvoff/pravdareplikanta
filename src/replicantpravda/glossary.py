"""Issue-local glossary extraction and conservative, offline mention matching."""

import re
import unicodedata
from dataclasses import dataclass

from .models import Article, Edition

RUSSIAN_ENDINGS = tuple(
    sorted(
        {
            "иями",
            "ями",
            "ами",
            "ией",
            "иям",
            "иях",
            "ого",
            "ему",
            "ому",
            "ыми",
            "ими",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ий",
            "ый",
            "ой",
            "ую",
            "юю",
            "ых",
            "их",
            "ым",
            "им",
            "ом",
            "ем",
            "ов",
            "ев",
            "ей",
            "ам",
            "ям",
            "ах",
            "ях",
            "ия",
            "ию",
            "ии",
            "ью",
            "а",
            "я",
            "ы",
            "и",
            "у",
            "ю",
            "е",
            "о",
        },
        key=lambda ending: (-len(ending), ending),
    )
)


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    definition: str


def glossary_entries(edition: Edition) -> list[GlossaryEntry]:
    glossary = next((article for article in edition.articles if article.id == "glossary"), None)
    if glossary is None:
        return []
    entries = []
    term = ""
    paragraphs: list[str] = []
    for block in glossary.body:
        if block.type == "heading":
            if term and paragraphs:
                entries.append(GlossaryEntry(term, "\n\n".join(paragraphs)))
            term, paragraphs = block.text, []
        elif term:
            paragraphs.extend(block.items if block.type == "list" else [block.text])
    if term and paragraphs:
        entries.append(GlossaryEntry(term, "\n\n".join(paragraphs)))
    return entries


def matching_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    # Compare kanji with or without kana readings; preserve the displayed source text.
    text = re.sub(r"\([\u3040-\u30ff\s]+\)", "", text)
    return " ".join(text.split())


def word_key(word: str, lang: str) -> str:
    if lang == "ru" and re.fullmatch(r"[а-я]+", word) and len(word) >= 4:
        for ending in RUSSIAN_ENDINGS:
            if word.endswith(ending) and len(word) - len(ending) >= 3:
                return word[: -len(ending)].rstrip("ь")
        return word.rstrip("ь")
    if re.fullmatch(r"[a-z]+", word):
        if len(word) > 4 and word.endswith("ies"):
            return word[:-3] + "y"
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
    return word


def mentions(term: str, text: str, lang: str) -> bool:
    term, text = matching_text(term), matching_text(text)
    if lang == "ja":
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", term):
            return term in text
        # Latin abbreviations next to Japanese particles are still separate terms.
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text))
    phrase = [word_key(word, lang) for word in re.findall(r"[^\W_]+", term)]
    words = [word_key(word, lang) for word in re.findall(r"[^\W_]+", text)]
    return bool(phrase) and any(
        words[start : start + len(phrase)] == phrase
        for start in range(len(words) - len(phrase) + 1)
    )


def article_glossary(
    article: Article,
    entries: list[GlossaryEntry],
    lang: str,
    aliases: dict[str, list[str]] | None = None,
) -> list[GlossaryEntry]:
    if article.id == "glossary":
        return []
    text = [article.headline, article.dek]
    for block in article.body:
        text.extend(block.items if block.type == "list" else [block.text])
    if article.image:
        text.append(article.image.caption)
    # Sources and other definitions must not make unrelated terms appear relevant.
    variants = {matching_text(term): values for term, values in (aliases or {}).items()}
    return [
        entry
        for entry in entries
        if any(
            mentions(term, "\n".join(text), lang)
            for term in (entry.term, *variants.get(matching_text(entry.term), []))
        )
    ]
