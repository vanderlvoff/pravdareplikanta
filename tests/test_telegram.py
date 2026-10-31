"""Offline announcement format and mocked sending; no Telegram requests in tests."""

import importlib.util
import json
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from replicantpravda.cli import main
from replicantpravda.render import load_issue
from replicantpravda.telegram import (
    CHANNEL,
    check_bot,
    clean_lead,
    make_announcement,
    send_announcement,
    validate_announcement,
)

TOKEN = "123456:abcdefghijklmnopqrstuvwxyz_123456789"


@pytest.mark.parametrize("can_post", [True, False])
def test_bot_health_checks_credentials_and_real_channel_rights_without_sending(
    monkeypatch, can_post
):
    calls = []

    def fake(request, **kwargs):
        calls.append(request)
        if request.full_url.endswith("/getMe"):
            return b'{"ok":true,"result":{"id":42,"is_bot":true}}'
        assert request.full_url.endswith("/getChatMember")
        assert json.loads(request.data) == {"chat_id": CHANNEL, "user_id": 42}
        return json.dumps(
            {"ok": True, "result": {"status": "administrator", "can_post_messages": can_post}}
        ).encode()

    monkeypatch.setattr("replicantpravda.telegram.request_bytes", fake)
    if can_post:
        check_bot(TOKEN)
    else:
        with pytest.raises(ValueError, match="permission"):
            check_bot(TOKEN)
    assert len(calls) == 2
    assert not any(request.full_url.endswith("/sendMessage") for request in calls)


@pytest.fixture
def issue():
    return load_issue(Path("content/issues/2026-10-29.json")).model_copy(
        update={"status": "approved"}
    )


def test_short_russian_announcement_has_one_permanent_link(issue):
    packet = make_announcement(issue)
    assert validate_announcement(packet) == packet
    assert packet["text"].count("https://") == 1
    assert packet["text"].endswith("https://repravda.com/ru/issues/2026-10-29/")
    assert "29 октября 2026" in packet["text"]
    assert "выпуск № 1" in packet["text"]
    assert len(packet["text"]) < 4096
    revised = issue.model_copy(update={"revision": 10})
    assert make_announcement(revised)["issue_id"] == packet["issue_id"]
    assert make_announcement(revised)["text"] == packet["text"]


def test_long_lead_urls_controls_and_empty_lead():
    text = clean_lead(("роботы " * 1000) + " https://example.org/secret\n\x1b")
    assert len(text) <= 440 and "https://" not in text and "\x1b" not in text
    assert clean_lead("Один\nвыпуск") == "Один выпуск"
    assert clean_lead(" ")


@pytest.mark.parametrize(
    "fault", ["draft", "number", "link", "text", "language", "extra", "bool", "type"]
)
def test_bad_announcement_is_rejected(issue, fault):
    packet = make_announcement(issue)
    if fault == "draft":
        packet["status"] = "draft"
    elif fault == "number":
        packet["number"] = 0
    elif fault == "link":
        packet["url"] = "https://evil.example/"
    elif fault == "text":
        packet["text"] += " bad"
    elif fault == "language":
        packet["language"] = "en"
    elif fault == "extra":
        packet["secret"] = "not allowed"
    elif fault == "bool":
        packet["version"] = True
    else:
        packet["lead"] = None
    with pytest.raises(ValueError):
        validate_announcement(packet)


def test_draft_and_nonprimary_issue_cannot_be_announced(issue):
    with pytest.raises(ValueError):
        make_announcement(issue.model_copy(update={"status": "draft"}))
    with pytest.raises(ValueError):
        make_announcement(issue.model_copy(update={"edition": "children"}))


def test_cli_preview_needs_no_token_and_never_requests_network(
    issue, tmp_path, monkeypatch, capsys
):
    path = tmp_path / "issue.json"
    path.write_text(issue.model_dump_json())
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(
        "replicantpravda.telegram.request_bytes", lambda *a, **k: pytest.fail("Network in preview")
    )
    monkeypatch.setattr("sys.argv", ["rp", "telegram", "--issue", str(path)])
    assert main() == 0
    assert "PREVIEW ONLY" in capsys.readouterr().out


def test_sender_plain_text_one_call_and_known_channel(issue, monkeypatch):
    calls = []

    def fake(request, **kwargs):
        calls.append(request)
        return b'{"ok":true,"result":{"message_id":42}}'

    monkeypatch.setattr("replicantpravda.telegram.request_bytes", fake)
    packet = make_announcement(issue)
    assert send_announcement(packet, TOKEN) == 42
    assert len(calls) == 1
    body = json.loads(calls[0].data)
    assert body["chat_id"] == CHANNEL == "@pravdareplicanta"
    assert body["text"] == packet["text"]
    assert "parse_mode" not in body
    assert body["link_preview_options"]["is_disabled"] is True


@pytest.mark.parametrize("fault", ["http", "timeout", "malformed"])
def test_sending_errors_hide_token_and_do_not_retry(issue, monkeypatch, fault):
    calls = []

    def fake(request, **kwargs):
        calls.append(request)
        if fault == "http":
            raise HTTPError(request.full_url, 401, TOKEN, None, None)
        if fault == "timeout":
            raise URLError(TOKEN)
        return b"[]"

    monkeypatch.setattr("replicantpravda.telegram.request_bytes", fake)
    with pytest.raises(ValueError) as error:
        send_announcement(make_announcement(issue), TOKEN)
    assert TOKEN not in str(error.value)
    assert len(calls) == 1


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("telegram_runner", "scripts/telegram_announce.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release(issue, tmp_path):
    import hashlib

    root = tmp_path / "public"
    root.mkdir()
    packet = make_announcement(issue)
    (root / "announcement.json").write_text(json.dumps(packet, ensure_ascii=False))
    folder = root / "ru/issues" / str(issue.issue_id)
    folder.mkdir(parents=True)
    (folder / "index.html").write_text("published html")
    (folder / "edition.pdf").write_bytes(b"%PDF-test")
    manifest = {
        "site_url": "https://repravda.com",
        "issues": [
            {
                "issue_id": str(issue.issue_id),
                "number": issue.number,
                "revision": issue.revision,
                "status": issue.status,
            }
        ],
        "files": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        },
    }
    path = tmp_path / "public.release.json"
    path.write_text(json.dumps(manifest))
    return root, path, packet, manifest


def success(runner, **changes):
    result = {
        "id": 10,
        "name": runner.CHECK_NAME,
        "app": {"id": runner.APP_ID, "slug": runner.APP_SLUG},
        "status": "completed",
        "conclusion": "success",
    }
    result.update(changes)
    return result


def test_only_correct_cloudflare_app_and_latest_success_are_accepted(runner):
    good = success(runner)
    assert runner.cloudflare_success([good])
    assert not runner.cloudflare_success([success(runner, app={"id": 0, "slug": "other"})])
    assert not runner.cloudflare_success([good, success(runner, id=11, conclusion="failure")])


def test_context_rejects_develop_forks_and_stale_commits(runner, monkeypatch):
    event = {
        "repository": {"full_name": runner.REPOSITORY},
        "ref": "refs/heads/main",
        "after": "a" * 40,
    }
    assert runner.verify_context(event, "push", "a" * 40, dry_run=False)
    assert not runner.verify_context(event, "push", "b" * 40, dry_run=False)
    event["ref"] = "refs/heads/develop"
    assert not runner.verify_context(event, "push", "a" * 40, dry_run=False)
    event["repository"]["full_name"] = "someone/fork"
    assert not runner.verify_context(event, "workflow_dispatch", "a" * 40, dry_run=True)


def test_live_hashes_prevent_stale_or_missing_publication(runner, release, monkeypatch):
    root, _, packet, manifest = release
    monkeypatch.setattr(
        runner,
        "fetch_public",
        lambda url: public_bytes(root, url),
    )
    runner.verify_live(packet, manifest)
    (root / "ru/issues" / packet["issue_id"] / "index.html").write_text("older release")
    with pytest.raises(ValueError, match="Published files"):
        runner.verify_live(packet, manifest)


def public_bytes(root, url):
    assert not url.endswith("index.html"), "Use the canonical Workers directory route"
    path = root / url.split("https://repravda.com/", 1)[1]
    return (path / "index.html" if url.endswith("/") else path).read_bytes()


def configure(runner, release, tmp_path, monkeypatch):
    root, manifest, packet, _ = release
    event = {
        "repository": {"full_name": runner.REPOSITORY},
        "ref": "refs/heads/main",
        "after": "a" * 40,
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("TELEGRAM_ANNOUNCEMENTS_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setattr(runner, "current_commit", lambda: "a" * 40)

    class FixedTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 1, 12, tzinfo=tz)

    monkeypatch.setattr(runner, "datetime", FixedTime)
    artifacts = []

    def fake_github(path):
        if path.startswith("actions/artifacts?"):
            return {"artifacts": artifacts}
        if path.startswith("commits/"):
            return {"check_runs": [success(runner)]}
        pytest.fail("Unexpected GitHub request")

    monkeypatch.setattr(runner, "github", fake_github)
    monkeypatch.setattr(
        runner,
        "fetch_public",
        lambda url: public_bytes(root, url),
    )
    return artifacts


def test_prepare_is_safe_and_durable_reservation_stops_duplicates(
    runner, release, tmp_path, monkeypatch
):
    artifacts = configure(runner, release, tmp_path, monkeypatch)
    root, manifest, packet, _ = release
    work = tmp_path / "work"
    sent = []
    monkeypatch.setattr(runner, "send_announcement", lambda *args: sent.append(args))
    result = runner.prepare(root, manifest, work, dry_run=False)
    assert result["send"] == "true" and not sent
    assert (work / "claim.json").exists()
    with pytest.raises(ValueError, match="reservation"):
        runner.send(root, manifest, work)
    artifacts.append({"name": result["artifact_name"]})  # Mock the upload action, before any send.
    runner.send(root, manifest, work)
    assert len(sent) == 1
    assert runner.prepare(root, manifest, work, dry_run=False)["send"] == "false"
    with pytest.raises(FileExistsError):
        runner.send(root, manifest, work)
    assert len(sent) == 1


def test_workflow_dry_run_creates_no_reservation_or_network_post(
    runner, release, tmp_path, monkeypatch
):
    configure(runner, release, tmp_path, monkeypatch)
    root, manifest, _, _ = release
    work = tmp_path / "work"
    monkeypatch.setattr(
        runner, "send_announcement", lambda *args: pytest.fail("Preview sent a message")
    )
    assert runner.prepare(root, manifest, work, dry_run=True)["send"] == "false"
    assert not work.exists()


def test_failed_deploy_stops_before_reserving(runner, release, tmp_path, monkeypatch):
    configure(runner, release, tmp_path, monkeypatch)
    monkeypatch.setattr(
        runner,
        "github",
        lambda path: {"artifacts": []}
        if path.startswith("actions/")
        else {"check_runs": [success(runner, conclusion="failure")]},
    )
    root, manifest, _, _ = release
    work = tmp_path / "work"
    with pytest.raises(ValueError, match="did not succeed"):
        runner.prepare(root, manifest, work, dry_run=False)
    assert not work.exists()


def test_runner_needs_only_standard_library():
    import os
    import subprocess
    import sys

    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    result = subprocess.run(
        [sys.executable, "-S", "scripts/telegram_announce.py", "--help"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
