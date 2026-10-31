"""Escaped static footnotes with source-preserving offsets and native anchors."""

import re
import unicodedata
from dataclasses import dataclass

from markupsafe import Markup, escape

from .glossary import GlossaryEntry, matching_text, word_key
from .models import Article


@dataclass(frozen=True)
class TermNote:
    term: str
    definition: str
    number: int


def normalized_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    chars: list[str] = []
    positions: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text) and (unicodedata.combining(text[end]) or text[end] in "\uff9e\uff9f"):
            end += 1
        value = unicodedata.normalize("NFKC", text[start:end]).casefold().replace("ё", "е")
        for char in value:
            chars.append(char)
            positions.append((start, end))
        start = end
    normalized = "".join(chars)
    ignored = set()
    for match in re.finditer(r"\([\u3040-\u30ff\s]+\)", normalized):
        ignored.update(range(match.start(), match.end()))
    result: list[str] = []
    offsets: list[tuple[int, int]] = []
    for index, char in enumerate(chars):
        if index in ignored:
            continue
        if char.isspace():
            if result and result[-1] == " ":
                offsets[-1] = (offsets[-1][0], positions[index][1])
                continue
            char = " "
        result.append(char)
        offsets.append(positions[index])
    return "".join(result), offsets


def mention_span(term: str, text: str, lang: str) -> tuple[int, int] | None:
    normalized, offsets = normalized_offsets(text)
    query = matching_text(term)
    span = None
    if lang == "ja":
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", query):
            start = normalized.find(query)
            if start >= 0:
                span = (start, start + len(query))
        else:
            match = re.search(r"(?<![a-z0-9])" + re.escape(query) + r"(?![a-z0-9])", normalized)
            if match:
                span = match.span()
    else:
        phrase = [word_key(word, lang) for word in re.findall(r"[^\W_]+", query)]
        tokens = list(re.finditer(r"[^\W_]+", normalized))
        words = [word_key(token.group(), lang) for token in tokens]
        if phrase:
            for start in range(len(words) - len(phrase) + 1):
                if words[start : start + len(phrase)] == phrase:
                    span = (tokens[start].start(), tokens[start + len(phrase) - 1].end())
                    break
    if span is None or span[0] == span[1]:
        return None
    first, last = offsets[span[0]][0], offsets[span[1] - 1][1]
    reading = re.match(r"[（(][\u3040-\u30ff\s]+[）)]", text[last:])
    if reading:
        last += reading.end()
    return first, last


def annotate_article(
    article: Article,
    entries: list[GlossaryEntry],
    lang: str,
    aliases: dict[str, list[str]],
    reference_label: str,
) -> dict:
    chunks = [article.headline, article.dek]
    caption_index = len(chunks)
    if article.image:
        chunks.append(article.image.caption)
    body_indexes = []
    for block in article.body:
        values = block.items if block.type == "list" else [block.text]
        body_indexes.append(list(range(len(chunks), len(chunks) + len(values))))
        chunks.extend(values)
    candidates = []
    variants = {matching_text(key): value for key, value in aliases.items()}
    if article.id != "glossary":
        for entry in entries:
            matches = []
            for index, chunk in enumerate(chunks):
                for query in (entry.term, *variants.get(matching_text(entry.term), [])):
                    span = mention_span(query, chunk, lang)
                    if span:
                        matches.append((index, span[0], span[1]))
                if matches:
                    break
            if matches:
                candidates.append((*min(matches), entry))
    candidates.sort(key=lambda item: (item[0], item[2], item[1]))
    insertions: dict[int, list[tuple[int, TermNote]]] = {}
    notes = []
    for number, (index, start, end, entry) in enumerate(candidates, 1):
        note = TermNote(entry.term, entry.definition, number)
        notes.append(note)
        insertions.setdefault(index, []).append((end, note))
    rendered = []
    for index, chunk in enumerate(chunks):
        parts = []
        previous = 0
        for end, note in sorted(
            insertions.get(index, []), key=lambda item: (item[0], item[1].number)
        ):
            parts.append(escape(chunk[previous:end]))
            label = f"{reference_label} {note.number}: {note.term}"
            parts.append(
                Markup(
                    '<sup class="term-reference"><a id="term-ref-{0}" href="#term-{0}" '
                    'role="doc-noteref" aria-label="{1}">[{0}]</a></sup>'
                ).format(note.number, label)
            )
            previous = end
        parts.append(escape(chunk[previous:]))
        rendered.append(Markup("").join(parts))
    return {
        "annotated_headline": rendered[0],
        "annotated_dek": rendered[1],
        "annotated_body": [
            [rendered[index] for index in indexes] if block.type == "list" else rendered[indexes[0]]
            for block, indexes in zip(article.body, body_indexes, strict=True)
        ],
        "annotated_caption": rendered[caption_index] if article.image else None,
        "article_glossary": notes,
    }
