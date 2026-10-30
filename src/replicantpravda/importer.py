"""Import the owner's per-language daily JSON without altering source files."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from .models import Article, Edition, Issue, Record, Slug, Source, Text


class FeedSource(Record):
    id: Slug
    url: HttpUrl
    domain: Text
    organization: Text
    published_at: date
    title: Text

    @model_validator(mode="after")
    def matching_domain(self) -> "FeedSource":
        host = urlsplit(str(self.url)).hostname or ""
        if host.removeprefix("www.") != self.domain.removeprefix("www."):
            raise ValueError("Source domain differs from source URL")
        return self


class FeedNews(Record):
    id: Slug
    title: Text
    body: Text | Annotated[list[Text], Field(min_length=1)] = Field(
        description="Reader-facing article text; no metadata fallback"
    )
    summary: str = ""
    details: str = ""
    technical_novelty: str = ""
    engineering_impact: str = ""
    limitations: str = ""
    evidence_status: str = ""
    published_at: date
    organization: Text
    time_window: Literal["24h", "72h", "7d"] | None = None
    source_ids: list[Slug] = Field(min_length=1)


class TechnologySignal(Record):
    title: Text
    summary: Text
    implications: Text


class GlossaryEntry(Record):
    term: Text
    definition: Text


class FeedEdition(Record):
    schema_version: Literal["1.0", "1.2"]
    publication: Literal["pravda_replikanta"]
    issue_type: Literal["daily"]
    issue_date: date
    issue_id: Text
    language: Literal["ru", "en", "ja", "jp"]
    generated_at: AwareDatetime
    title: Text
    lead: Text
    news: list[FeedNews] = Field(min_length=1)
    technology_signal: TechnologySignal
    glossary: list[GlossaryEntry] = Field(min_length=1)
    sources: list[FeedSource] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self) -> "FeedEdition":
        if self.issue_id != f"daily-{self.issue_date}":
            raise ValueError("Feed issue_id differs from issue_date")
        ids = [item.id for item in self.news]
        source_ids = [item.id for item in self.sources]
        if len(ids) != len(set(ids)) or len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate news or source ID in feed")
        if set(ids) & {"technology-signal", "glossary"}:
            raise ValueError("News uses a reserved section ID")
        for item in self.news:
            if len(item.source_ids) != len(set(item.source_ids)):
                raise ValueError(f"Duplicate source reference in {item.id}")
            if not set(item.source_ids) <= set(source_ids):
                raise ValueError(f"Unknown source reference in {item.id}")
            if item.published_at > self.issue_date:
                raise ValueError(f"Future news date in {item.id}")
        if any(source.published_at > self.issue_date for source in self.sources):
            raise ValueError("Future source date")
        return self


def import_feed(folder: Path, template: Issue, *, number: int, revision: int) -> tuple[Issue, dict]:
    """Return normalized data plus provenance, preserving all editorial sections."""
    labels = json.loads(
        Path(__file__)
        .with_name("templates")
        .joinpath("import-labels.json")
        .read_text(encoding="utf-8")
    )
    feeds = {}
    provenance = {}
    for lang in ("ru", "en", "ja"):
        path = folder / f"{lang}.json"
        if lang == "ja":
            alias = folder / "jp.json"
            if path.exists() and alias.exists():
                raise ValueError("Both ja.json and jp.json exist; choose one Japanese edition")
            if alias.exists():
                path = alias
        raw = path.read_bytes()
        feed = FeedEdition.model_validate_json(raw)
        normalized_language = "ja" if feed.language == "jp" else feed.language
        if normalized_language != lang:
            raise ValueError(f"Language does not match filename: {path.name}")
        feeds[lang] = feed
        provenance[lang] = {
            "file": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "metadata": feed.model_dump(
                mode="json", exclude={"news", "technology_signal", "glossary", "sources"}
            ),
        }
    reference = feeds["ru"]
    reference_ids = {item.id for item in reference.news}
    for feed in feeds.values():
        if feed.issue_date != reference.issue_date or feed.issue_id != reference.issue_id:
            raise ValueError("Language editions have different issue dates/IDs")
        if {item.id for item in feed.news} != reference_ids:
            raise ValueError("News IDs differ across language editions")
        if len(feed.glossary) != len(reference.glossary):
            raise ValueError("Glossary entries missing in a language edition")
        identity = {(s.id, str(s.url), s.published_at) for s in feed.sources}
        if identity != {(s.id, str(s.url), s.published_at) for s in reference.sources}:
            raise ValueError("Source IDs, URLs or dates differ across language editions")
    editions = {}
    for lang, feed in feeds.items():
        words = labels[lang]
        sources = {
            source.id: Source(url=source.url, title=source.title, published_at=source.published_at)
            for source in feed.sources
        }
        articles = []
        for item in feed.news:
            paragraphs = (
                re.split(r"\n+", item.body.replace("\r\n", "\n"))
                if isinstance(item.body, str)
                else item.body
            )
            blocks = [
                {"type": "paragraph", "text": paragraph.strip()}
                for paragraph in paragraphs
                if paragraph.strip()
            ]
            articles.append(
                Article(
                    id=item.id,
                    slug=item.id,
                    category="news",
                    headline=item.title,
                    dek="",
                    body=blocks,
                    sources=[sources[key] for key in item.source_ids],
                )
            )
        signal = feed.technology_signal
        articles.append(
            Article(
                id="technology-signal",
                slug="technology-signal",
                category="analysis",
                headline=signal.title,
                dek=signal.summary,
                body=[{"type": "paragraph", "text": signal.implications}],
                sources=list(sources.values()),
            )
        )
        blocks = []
        for entry in feed.glossary:
            blocks.extend(
                [
                    {"type": "heading", "text": entry.term},
                    {"type": "paragraph", "text": entry.definition},
                ]
            )
        articles.append(
            Article(
                id="glossary",
                slug="glossary",
                category="analysis",
                headline=words["glossary"],
                dek=words["glossary_dek"],
                body=blocks,
                sources=list(sources.values()),
            )
        )
        editions[lang] = Edition(
            title=template.languages[lang].title,
            weather=(
                template.languages[lang].weather
                if template.languages[lang].weather
                and template.languages[lang].weather.forecast_date == reference.issue_date
                else None
            ),
            issue_title=feed.title,
            editorial_note=feed.lead,
            articles=articles,
        )
    weather = (
        template.weather
        if template.weather and template.weather.forecast_date == reference.issue_date
        else None
    )
    issue = Issue(
        issue_id=reference.issue_date,
        publication_date=reference.issue_date,
        number=number,
        revision=revision,
        status="draft",
        languages=editions,
        weather=weather,
    )
    return issue, {
        "status": "draft",
        "sources": provenance,
        "pagination": "automatic",
        "review_required": [
            "facts and source claims",
            "translations",
            "print overflow",
            "visual review",
        ],
    }


def save_import(
    folder: Path, template: Issue, output: Path, *, number: int, revision: int
) -> Issue:
    report_path = output.with_suffix(".import.json")
    if output.exists() or report_path.exists():
        raise ValueError("Import output/report already exists; choose a new path")
    issue, report = import_feed(folder, template, number=number, revision=revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(issue.model_dump_json(indent=2) + "\n")
    with report_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return issue
