import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from replicantpravda.cli import main
from replicantpravda.models import Issue
from replicantpravda.render import build, load_issue


@pytest.fixture
def data():
    return json.loads(Path("content/issues/2026-10-29.json").read_text())


@pytest.mark.parametrize("language", ["ru", "en", "ja"])
def test_unicode_and_breaks(data, tmp_path, language):
    issue = Issue.model_validate(data)
    build(issue, tmp_path / "site")
    html = (tmp_path / "site" / language / "articles/robot-evaluation/index.html").read_text()
    assert issue.languages[language].articles[0].body[0].text in html
    assert f'lang="{language}"' in html
    assert "\n" in issue.languages[language].articles[0].body[0].text


@pytest.mark.parametrize("change", ["missing", "ids", "duplicate", "url", "unknown", "empty"])
def test_reject_invalid(data, change):
    article = data["languages"]["en"]["articles"][0]
    if change == "missing":
        del data["languages"]["ja"]
    elif change == "ids":
        article["id"] = "different"
    elif change == "duplicate":
        data["languages"]["en"]["articles"].append(article.copy())
    elif change == "url":
        article["sources"][0]["url"] = "javascript:alert(1)"
    elif change == "unknown":
        article["body"] = [{"type": "html", "text": "<script>"}]
    else:
        article["headline"] = " "
    with pytest.raises(ValidationError):
        Issue.model_validate(data)


def test_escape_and_determinism(data, tmp_path):
    data["languages"]["en"]["articles"][0]["headline"] = "<script>alert(1)</script>"
    issue = Issue.model_validate(data)
    for name in ("one", "two"):
        build(issue, tmp_path / name)
    for path in (tmp_path / "one").rglob("*"):
        if path.is_file():
            assert (
                path.read_bytes()
                == (tmp_path / "two" / path.relative_to(tmp_path / "one")).read_bytes()
            )
    html = (tmp_path / "one/en/articles/robot-evaluation/index.html").read_text()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "editorial_note" not in html
    with pytest.raises(ValueError, match="already exists"):
        build(issue, tmp_path / "one")


def test_sample_and_cli(monkeypatch, tmp_path):
    assert load_issue(Path("content/issues/2026-10-29.json")).status == "draft"
    monkeypatch.setattr(
        "sys.argv", ["rp", "build", "--issue", "2026-10-29", "--output", str(tmp_path / "site")]
    )
    assert main() == 0
    report = json.loads((tmp_path / "site/verification.json").read_text())
    assert report["preview_only"] is True
