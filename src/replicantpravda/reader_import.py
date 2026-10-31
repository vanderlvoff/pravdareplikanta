"""Explicit local multi-edition feed inputs; invalid editions never get empty pages."""

from pathlib import Path

from .importer import import_feed
from .models import Issue
from .readers import READER_EDITIONS, reader_groups


def import_readers(
    latest: Path,
    template: Issue,
    *,
    number: int,
    revision: int = 1,
    archives: tuple[Path, ...] = (),
    legacy_issues: tuple[Issue, ...] = (),
) -> tuple[list[Issue], dict]:
    """Require a valid RU/EN/JA set for availability, reporting every rejected input.

    Archive inputs are explicit date folders, never revisions/ or rolling legacy
    feeds discovered recursively. Their issue number is read from a same-date
    legacy issue, or the caller must first normalize them with rp import.
    """
    issues = list(legacy_issues)
    reports: dict = {"inputs": [], "unavailable": {}, "publication": "DISABLED"}
    for folder in (*archives, latest):
        for code in READER_EDITIONS:
            path = folder / code
            if not path.exists():
                reports["inputs"].append({"folder": str(path), "status": "missing"})
                continue
            try:
                # Archive numbers cannot be inferred safely from calendar dates.
                archive_template = (
                    next(
                        (
                            i
                            for i in legacy_issues
                            if folder.as_posix().endswith(i.issue_id.strftime("%Y/%m/%d"))
                        ),
                        None,
                    )
                    if folder != latest
                    else None
                )
                if folder != latest and archive_template is None:
                    raise ValueError(
                        "Archive input needs an explicit same-date --legacy-issue for numbering"
                    )
                issue, provenance = import_feed(
                    path,
                    archive_template or template,
                    number=archive_template.number if archive_template else number,
                    revision=revision,
                )
                if issue.edition != code:
                    raise ValueError("Folder name differs from feed edition")
                if archive_template and issue.issue_id != archive_template.issue_id:
                    raise ValueError("Archive folder date differs from feed issue_date")
                if folder == latest and issue.issue_id != template.issue_id:
                    raise ValueError("Latest feed date differs from --template issue date")
                # Explicit v1.4 data replace a same-audience/date legacy source.
                issues = [i for i in issues if (i.edition, i.issue_id) != (code, issue.issue_id)]
                issues.append(issue)
                reports["inputs"].append(
                    {
                        "folder": str(path),
                        "status": "valid",
                        "edition": code,
                        "issue_id": str(issue.issue_id),
                        "provenance": provenance,
                    }
                )
            except (ValueError, OSError) as error:
                reports["inputs"].append(
                    {
                        "folder": str(path),
                        "status": "invalid",
                        "reason": str(error),
                    }
                )
    groups = reader_groups(issues)
    for code in READER_EDITIONS:
        if code not in groups:
            reports["unavailable"][code] = "No valid complete RU/EN/JA issue"
    if not groups:
        raise ValueError("No valid reader edition; check the RU/EN/JA feeds")
    return [issue for selected in groups.values() for issue in selected], reports
