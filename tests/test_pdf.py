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


def test_print_page_rejects_out_of_range(issue):
    from pydantic import ValidationError

    data = issue.model_dump()
    data["languages"]["ru"]["articles"][0]["print_page"] = 4
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
    assert any("3 pages" in error for error in report["errors"])
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
def test_three_localized_pdfs_and_overflow(issue, tmp_path):
    pytest.importorskip("playwright")
    pytest.importorskip("pymupdf")
    site = tmp_path / "complete"
    build(issue, site, pdf=True)
    report = verify_snapshot(site, str(issue.issue_id))
    assert report["passed"]
    for lang in ("ru", "en", "ja"):
        assert report["editions"][lang]["page_count"] == 3
        folder = site / lang / "issues" / str(issue.issue_id)
        assert all((folder / f"page-{page}.png").is_file() for page in (1, 2, 3))
    repeat = tmp_path / "repeat"
    build(issue, repeat, pdf=True)
    for lang in ("ru", "en", "ja"):
        relative = Path(lang) / "issues" / str(issue.issue_id) / "edition.pdf"
        assert (site / relative).read_bytes() == (repeat / relative).read_bytes()
    data = issue.model_dump()
    data["languages"]["ru"]["articles"][0]["body"] = [
        {"type": "paragraph", "text": "Переполнение текста. " * 8000}
    ]
    overflow = tmp_path / "overflow"
    with pytest.raises(ValueError, match="report"):
        build(Issue.model_validate(data), overflow, pdf=True)
    assert not overflow.exists()
    failed = json.loads((tmp_path / "overflow.failed.json").read_text())
    assert failed["editions"]["ru"]["overflow"]
    assert any(
        problem.get("article") == "robot-evaluation"
        or "robot-evaluation" in problem.get("articles", [])
        for problem in failed["editions"]["ru"]["overflow"]
    )
