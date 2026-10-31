"""Exercise API payloads and failure handling without spending tokens."""

import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

import pytest

from replicantpravda.editorial import (
    DraftResult,
    assemble_issue,
    generate_draft,
    post_response,
    response_text,
)
from replicantpravda.render import load_issue

DAY = date(2026, 10, 29)
URL = "https://example.org/research"


@pytest.fixture
def template():
    return load_issue(Path("content/issues/2026-10-29.json"))


@pytest.fixture
def wire(template):
    return {
        "ready": True,
        "missing_information": [],
        "editions": [
            {
                "language": lang,
                "editorial_note": "Draft only",
                "articles": [
                    {
                        "id": article.id,
                        "slug": article.slug,
                        "category": "analysis",
                        "headline": article.headline,
                        "dek": article.dek,
                        "paragraphs": ["Test fixture only"],
                        "sources": [
                            {
                                "url": URL,
                                "title": "Test fixture source",
                                "published_at": "2026-10-28",
                            }
                        ],
                        "print_page": article.print_page,
                    }
                    for article in edition.articles
                ],
            }
            for lang, edition in template.languages.items()
        ],
    }


def envelope(text):
    return {
        "id": "fixture-response",
        "status": "completed",
        "usage": {"total_tokens": 100},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
    }


def research():
    result = envelope("Test research only")
    result["output"].insert(
        0, {"type": "web_search_call", "status": "completed", "action": {"sources": [{"url": URL}]}}
    )
    return result


def test_dry_run_needs_no_key_or_network(template, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "replicantpravda.editorial.post_response",
        lambda *args: pytest.fail("Unexpected API request"),
    )
    output = tmp_path / "draft"
    report = generate_draft(
        template=template, day=DAY, number=2, output=output, model="fixture-model", dry_run=True
    )
    assert report["requests"] == 2
    assert report["status"] == "dry_run"
    assert not output.exists()


def test_missing_key(template, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY locally"):
        generate_draft(
            template=template, day=DAY, number=2, output=tmp_path / "draft", model="fixture-model"
        )


def test_successful_two_request_draft(template, wire, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-value")
    calls = []

    def send(payload, key):
        assert key == "secret-test-value"
        calls.append(payload)
        return research() if len(calls) == 1 else envelope(json.dumps(wire))

    monkeypatch.setattr("replicantpravda.editorial.post_response", send)
    output = tmp_path / "draft"
    report = generate_draft(
        template=template, day=DAY, number=2, output=output, model="fixture-model"
    )
    issue = load_issue(output / f"{DAY}.json")
    assert issue.status == "approved" and issue.weather is None
    assert report["status"] == "approved"
    assert report["review_stage"] == "cloudflare_upload"
    assert all(payload["store"] is False for payload in calls)
    assert calls[0]["tools"] == [{"type": "web_search"}]
    assert calls[0]["tool_choice"] == "required"
    assert calls[1]["text"]["format"]["strict"] is True
    assert len(calls) == 2
    assert not any("secret-test-value" in path.read_text() for path in output.iterdir())
    with pytest.raises(ValueError, match="output exists"):
        generate_draft(template=template, day=DAY, number=2, output=output, model="fixture-model")
    assert len(calls) == 2


@pytest.mark.parametrize("fault", ["url", "date", "missing_language", "not_ready", "article_count"])
def test_reject_unreliable_editorial(wire, template, fault):
    if fault == "url":
        wire["editions"][0]["articles"][0]["sources"][0]["url"] = "https://example.net/invented"
    elif fault == "date":
        wire["editions"][0]["articles"][0]["sources"][0]["published_at"] = "2026-11-01"
    elif fault == "missing_language":
        wire["editions"].pop()
    elif fault == "not_ready":
        wire["ready"] = False
    else:
        wire["editions"][0]["articles"].pop()
    with pytest.raises(ValueError):
        assemble_issue(DraftResult.model_validate(wire), template, DAY, 2, {URL})


@pytest.mark.parametrize("fault", ["no_search", "incomplete", "refusal", "network"])
def test_failures_never_save_issue(template, monkeypatch, tmp_path, fault):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-value")
    calls = []

    def send(*args):
        calls.append(1)
        if fault == "network":
            raise ValueError("Network unavailable")
        if fault == "no_search":
            return envelope("No research")
        if fault == "incomplete":
            return {"status": "incomplete"}
        return {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "refusal", "refusal": "Test refusal"}]}
            ],
        }

    monkeypatch.setattr("replicantpravda.editorial.post_response", send)
    output = tmp_path / "draft"
    with pytest.raises(ValueError, match="No canonical issue was changed"):
        generate_draft(template=template, day=DAY, number=2, output=output, model="fixture-model")
    assert len(calls) == 1
    assert not (output / f"{DAY}.json").exists()
    assert json.loads((output / "run.json").read_text())["status"] == "failed"


def test_provider_errors_do_not_expose_key(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError("https://api.openai.com", 401, "secret-test-value", {}, None)

    monkeypatch.setattr("replicantpravda.editorial.urlopen", fail)
    with pytest.raises(ValueError) as error:
        post_response({}, "secret-test-value")
    assert "401" in str(error.value)
    assert "secret-test-value" not in str(error.value)


def test_refusal_is_not_treated_as_text():
    with pytest.raises(ValueError):
        response_text({"status": "completed", "output": []})


@pytest.mark.parametrize(
    "code",
    ["insufficient_quota", "credit_balance_exhausted", "rate_limit_exceeded", "model_not_found"],
)
def test_safe_error_retains_code_without_server_message(monkeypatch, code):
    from io import BytesIO

    def fail(*args, **kwargs):
        body = {"error": {"code": code, "message": "secret-test-value"}}
        raise HTTPError(
            "https://api.openai.com",
            429,
            "error",
            {"Retry-After": "20"},
            BytesIO(json.dumps(body).encode()),
        )

    monkeypatch.setattr("replicantpravda.editorial.urlopen", fail)
    with pytest.raises(ValueError) as error:
        post_response({}, "secret-test-value")
    message = str(error.value)
    assert code in message
    assert "secret-test-value" not in message
    assert "Retry-After: 20 seconds" in message


def test_unknown_error_code_is_not_echoed(monkeypatch):
    from io import BytesIO

    def fail(*args, **kwargs):
        body = {"error": {"code": "secret-test-value", "message": "secret-test-value"}}
        raise HTTPError(
            "https://api.openai.com", 429, "error", {}, BytesIO(json.dumps(body).encode())
        )

    monkeypatch.setattr("replicantpravda.editorial.urlopen", fail)
    with pytest.raises(ValueError) as error:
        post_response({}, "secret-test-value")
    assert "secret-test-value" not in str(error.value)
