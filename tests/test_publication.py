"""Only verified publication output may enter the GitHub static-assets bundle."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from replicantpravda.publication import prepare_release, reader_file
from replicantpravda.render import build, load_issue


@pytest.fixture
def issue():
    return load_issue(Path("content/issues/2026-10-29.json")).model_copy(
        update={"status": "approved"}
    )


def test_publication_is_explicit_and_rejects_drafts(issue, tmp_path):
    draft = issue.model_copy(update={"status": "draft"})
    with pytest.raises(ValueError, match="approved/published"):
        build(draft, tmp_path / "bad", publication=True)
    assert not (tmp_path / "bad").exists()
    build(issue, tmp_path / "publication", publication=True)
    build(issue, tmp_path / "preview")
    for lang in ("ru", "en", "ja"):
        public = (tmp_path / "publication" / lang / "index.html").read_text()
        preview = (tmp_path / "preview" / lang / "index.html").read_text()
        assert 'content="noindex,nofollow"' not in public
        assert 'content="noindex,nofollow"' in preview
        assert "<small>" not in public
        assert "approved ·" not in public
    assert "Allow: /" in (tmp_path / "publication/robots.txt").read_text()
    with pytest.raises(ValueError, match="preview snapshots"):
        prepare_release(tmp_path / "preview", tmp_path / "release")
    with pytest.raises(ValueError, match="requires verified PDFs"):
        prepare_release(tmp_path / "publication", tmp_path / "release")


@pytest.mark.parametrize(
    "name",
    [
        "index.html",
        "style.css",
        "ru/rss.xml",
        "ru/archive/index.html",
        "ja/issues/2026-10-31/edition.pdf",
        "en/issues/2026-10-30/articles/robot/index.html",
        "assets/fonts/Caveat/OFL.txt",
        "data/images/2026-10-31/robot.webp",
    ],
)
def test_reader_files_are_selected(name):
    assert reader_file(name)


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        "source.json",
        "sources/2026-10-31.json",
        "verification.json",
        "artifacts.json",
        "ru/issues/2026-10-31/pagination.json",
        "ru/issues/2026-10-31/page-1.png",
        "ru/issues/2026-10-31/print/index.html",
        "ru/print/index.html",
        "data/latest/ru.json",
    ],
)
def test_internal_files_are_not_selected(name):
    assert not reader_file(name)


@pytest.mark.skipif(os.environ.get("RP_TEST_PDF") != "1", reason="Set RP_TEST_PDF=1 for Chromium")
def test_release_and_cloudflare_guard_reject_changed_files(issue, tmp_path):
    snapshot, public = tmp_path / "snapshot", tmp_path / "public"
    build(issue, snapshot, publication=True, pdf=True)
    report = prepare_release(snapshot, public)
    assert report["uploaded"] is False
    assert not (public / "source.json").exists()
    assert not list(public.rglob("*.json"))
    assert not list(public.glob("*/issues/*/page-*.png"))
    assert not list(public.glob("*/issues/*/print/index.html"))
    assert not (public / "print.css").exists()
    assert (public / "404.html").exists()
    for lang in ("ru", "en", "ja"):
        assert (public / lang / f"issues/{issue.issue_id}/edition.pdf").exists()
    manifest = json.loads(public.with_name("public.release.json").read_text())
    assert manifest["issues"][0]["status"] == "approved"
    before = (public / "index.html").read_bytes()
    with pytest.raises(ValueError, match="exists"):
        prepare_release(snapshot, public)
    assert before == (public / "index.html").read_bytes()
    if shutil.which("node"):
        command = ["node", "scripts/check-public.mjs", str(public)]
        good = subprocess.run(command, capture_output=True, text=True)
        assert good.returncode == 0, good.stderr
        (public / "style.css").write_text("changed")
        bad = subprocess.run(command, capture_output=True, text=True)
        assert bad.returncode != 0
        assert "changed release file" in bad.stderr
