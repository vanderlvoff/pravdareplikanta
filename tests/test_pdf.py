"""PDF verification failures and optional real Chromium integration."""

import json
import os
from pathlib import Path

import pytest

from replicantpravda.models import Issue
from replicantpravda.render import build, load_issue
from replicantpravda.verification import artifact_hashes, verify_pdf, verify_snapshot


@pytest.fixture
def issue():
    return load_issue(Path("content/issues/2026-10-29.json"))


def test_legacy_print_page_accepts_positive_hint(issue):
    from pydantic import ValidationError

    data = issue.model_dump()
    data["languages"]["ru"]["articles"][0]["print_page"] = 4
    assert Issue.model_validate(data).languages["ru"].articles[0].print_page == 4
    data["languages"]["ru"]["articles"][0]["print_page"] = 0
    with pytest.raises(ValidationError):
        Issue.model_validate(data)


def test_incomplete_pdf_is_rejected(issue, tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "bad.pdf"
    with pymupdf.open() as document:
        document.new_page(width=300, height=400)
        document.save(path)
    report = verify_pdf(path, issue, "en")
    assert not report["passed"]
    assert any("A4" in error for error in report["errors"])
    assert any("missing article text" in error for error in report["errors"])
    assert any("Caveat" in error for error in report["errors"])


def test_changed_snapshot_is_rejected(issue, tmp_path):
    (tmp_path / "source.json").write_text(issue.model_dump_json())
    (tmp_path / "artifacts.json").write_text(json.dumps(artifact_hashes(tmp_path)))
    (tmp_path / "source.json").write_text("{}")
    with pytest.raises(ValueError, match="changed or are missing"):
        verify_snapshot(tmp_path, str(issue.issue_id))


@pytest.mark.skipif(
    os.environ.get("RP_TEST_PDF") != "1", reason="Set RP_TEST_PDF=1 for real Chromium"
)
def test_localized_automatic_pagination(issue, tmp_path):
    pytest.importorskip("playwright")
    pytest.importorskip("pymupdf")
    site = tmp_path / "complete"
    build(issue, site, pdf=True)
    report = verify_snapshot(site, str(issue.issue_id))
    assert report["passed"]
    for lang in ("ru", "en", "ja"):
        count = report["editions"][lang]["page_count"]
        assert count >= 1
        folder = site / lang / "issues" / str(issue.issue_id)
        assert all((folder / f"page-{page}.png").is_file() for page in range(1, count + 1))
    repeat = tmp_path / "repeat"
    build(issue, repeat, pdf=True)
    for lang in ("ru", "en", "ja"):
        relative = Path(lang) / "issues" / str(issue.issue_id) / "edition.pdf"
        assert (site / relative).read_bytes() == (repeat / relative).read_bytes()
    data = issue.model_dump()
    data["languages"]["ru"]["articles"][0]["body"] = [
        {"type": "paragraph", "text": "Переполнение текста. " * 900}
    ]
    long_site = tmp_path / "long"
    build(Issue.model_validate(data), long_site, pdf=True)
    extended = verify_snapshot(long_site, str(issue.issue_id))
    assert extended["passed"]
    assert extended["editions"]["ru"]["page_count"] > 3

    # Adding pages must not silently accept an indivisible block that clips a column.
    data["languages"]["ru"]["articles"][0]["body"] = [
        {"type": "quote", "text": "Неразрывная цитата. " * 2000}
    ]
    broken = tmp_path / "unplaceable"
    with pytest.raises(ValueError, match="report"):
        build(Issue.model_validate(data), broken, pdf=True)
    assert not broken.exists()
    failed = json.loads((tmp_path / "unplaceable.failed.json").read_text())
    assert failed["editions"]["ru"]["overflow"]
