"""Explicit selection of historical issues; never discover editorial drafts by glob."""

from .models import Issue


def collect_issues(latest: Issue, history: tuple[Issue, ...]) -> list[Issue]:
    """Select one revision per date for a local, non-public review snapshot."""
    issues = [latest, *history]
    if any(issue.edition != latest.edition for issue in issues):
        raise ValueError("Archive history must belong to the same reader edition")
    ids = [issue.issue_id for issue in issues]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate archive issue date; select one revision per issue")
    for issue in issues:
        if issue.issue_id != issue.publication_date:
            raise ValueError("Archive issue_id must match publication_date")
        if issue.publication_date > latest.publication_date:
            raise ValueError("Archive issue cannot be newer than the selected latest issue")
    return sorted(issues, key=lambda issue: issue.publication_date, reverse=True)


def archive_metadata(issue: Issue) -> dict:
    return {
        "issue_id": str(issue.issue_id),
        "number": issue.number,
        "publication_date": str(issue.publication_date),
        "revision": issue.revision,
        "status": issue.status,
    }
