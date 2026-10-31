"""Reader edition routes and navigation, independent of language editions."""

from datetime import date

from .archive import collect_issues
from .models import Issue, ReaderEdition

READER_EDITIONS: tuple[ReaderEdition, ...] = (
    "engineer",
    "business",
    "enthusiast",
    "children",
)


def reader_base(lang: str, edition: str = "engineer") -> str:
    """Keep historical engineering URLs; scope other audiences below language."""
    return f"/{lang}/" if edition == "engineer" else f"/{lang}/{edition}/"


def source_path(issue: Issue) -> str:
    prefix = "" if issue.edition == "engineer" else f"{issue.edition}/"
    return f"sources/{prefix}{issue.issue_id}.json"


def reader_issue_key(issue: Issue) -> str:
    return (
        str(issue.issue_id) if issue.edition == "engineer" else f"{issue.edition}/{issue.issue_id}"
    )


def reader_groups(issues: list[Issue]) -> dict[ReaderEdition, list[Issue]]:
    groups = {}
    for code in READER_EDITIONS:
        selected = [issue for issue in issues if issue.edition == code]
        if selected:
            selected.sort(key=lambda issue: issue.publication_date, reverse=True)
            groups[code] = collect_issues(selected[0], tuple(selected[1:]))
    return groups


def reader_choices(
    groups: dict[ReaderEdition, list[Issue]],
    lang: str,
    active: ReaderEdition,
    words: dict,
    *,
    page: str = "home",
    issue_date: date | None = None,
    article_id: str | None = None,
) -> list[dict]:
    """Preserve article IDs/date where present, otherwise offer a real issue/home."""
    choices = []
    for code in READER_EDITIONS:
        selected = groups.get(code, [])
        url = None
        if selected:
            base = reader_base(lang, code)
            match = next((issue for issue in selected if issue.issue_id == issue_date), None)
            url = base
            if page in {"archive", "about"}:
                url += page + "/"
            elif match and page in {"issue", "article"}:
                url += f"issues/{match.issue_id}/"
                if page == "article":
                    article = next(
                        (a for a in match.languages[lang].articles if a.id == article_id), None
                    )
                    if article:
                        url += f"articles/{article.slug}/"
        choices.append(
            {
                "code": code,
                "label": words["editions"][code],
                "url": url,
                "active": code == active,
            }
        )
    return choices
