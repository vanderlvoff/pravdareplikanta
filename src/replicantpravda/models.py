"""Strict portable editorial input, independent of rendering."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Text = Annotated[str, Field(min_length=1)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(Record):
    url: HttpUrl
    title: Text
    published_at: date
    retrieved_at: date | None = None


class TextBlock(Record):
    type: Literal["paragraph", "heading", "quote", "caption"]
    text: Text


class ListBlock(Record):
    type: Literal["list"]
    items: list[Text] = Field(min_length=1)


class Article(Record):
    id: Slug
    slug: Slug
    category: Literal["news", "analysis", "opinion", "satire"]
    headline: Text
    dek: Text
    body: list[Annotated[TextBlock | ListBlock, Field(discriminator="type")]] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    image_asset_id: None = None


class Edition(Record):
    title: Text
    editorial_note: str = ""
    articles: list[Article] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_articles(self) -> "Edition":
        for key in ("id", "slug"):
            values = [getattr(article, key) for article in self.articles]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate article {key}")
        return self


class Issue(Record):
    issue_id: date
    number: int = Field(gt=0)
    publication_date: date
    revision: int = Field(gt=0)
    status: Literal["draft", "review", "approved", "published"]
    languages: dict[Literal["ru", "en", "ja"], Edition]

    @model_validator(mode="after")
    def parallel_editions(self) -> "Issue":
        if set(self.languages) != {"ru", "en", "ja"}:
            raise ValueError("All RU, EN and JA editions are required")
        ids = [{a.id for a in edition.articles} for edition in self.languages.values()]
        if any(value != ids[0] for value in ids):
            raise ValueError("Article IDs must match across editions")
        return self
