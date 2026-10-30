"""Strict portable editorial input, independent of rendering."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .weather import Weather

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


class ArticleImage(Record):
    url: HttpUrl
    path: Annotated[
        str, Field(pattern=r"^data/images/\d{4}-\d{2}-\d{2}/[a-z0-9]+(?:-[a-z0-9]+)*\.webp$")
    ]
    type: Literal["generated"]
    caption: Text
    alt: Text

    @model_validator(mode="after")
    def local_repository_source(self) -> "ArticleImage":
        expected = (
            "https://raw.githubusercontent.com/vanderlvoff/pravdareplikanta/main/" + self.path
        )
        if str(self.url) != expected:
            raise ValueError("Illustration URL must match its local repository path")
        return self


class Article(Record):
    id: Slug
    slug: Slug
    category: Literal["news", "analysis", "opinion", "satire"]
    headline: Text
    dek: str = ""
    body: list[Annotated[TextBlock | ListBlock, Field(discriminator="type")]] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)
    image: ArticleImage | None = None
    image_asset_id: None = None
    print_page: int = Field(
        default=1, ge=1, description="Legacy hint; automatic pagination ignores this field"
    )


class Edition(Record):
    title: Text
    weather: Weather | None = None
    issue_title: str = ""
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
    weather: Weather | None = None

    @model_validator(mode="after")
    def parallel_editions(self) -> "Issue":
        if self.weather and self.weather.forecast_date != self.publication_date:
            raise ValueError("Weather date must match issue publication_date")
        if any(
            edition.weather and edition.weather.forecast_date != self.publication_date
            for edition in self.languages.values()
        ):
            raise ValueError("Edition weather date must match issue publication_date")
        if set(self.languages) != {"ru", "en", "ja"}:
            raise ValueError("All RU, EN and JA editions are required")
        ids = [{a.id for a in edition.articles} for edition in self.languages.values()]
        if any(value != ids[0] for value in ids):
            raise ValueError("Article IDs must match across editions")
        return self
