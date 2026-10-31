"""Daily scheduling and publication decisions, without external writes."""

import importlib.util
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from replicantpravda.daily_build import data_digest, load_history, prepare


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launch_agent_is_daily_local_and_explicitly_authorized():
    installer = load_script("install_daily_publish")
    state = Path("/Users/example/Library/Application Support/ReplicantPravda")
    plist = installer.launch_agent(state, "/opt/homebrew/bin/node", "/opt/homebrew/bin/gh")
    assert plist["StartCalendarInterval"] == {"Hour": 6, "Minute": 20}
    assert plist["EnvironmentVariables"]["TZ"] == "Asia/Tokyo"
    assert plist["ProgramArguments"][-1] == "--push"
    assert plist["RunAtLoad"] is False
    assert plist["ProgramArguments"][0] == "/usr/bin/caffeinate"
    assert "TOKEN" not in json.dumps(plist)


@pytest.fixture
def daily_data(tmp_path):
    root = tmp_path / "checkout"
    feeds = Path("data/archive/2026/10/31/revisions/before-0.2-refresh-20261031T132532Z")
    shutil.copytree(feeds, root / "data/latest")
    (root / "content/technical").mkdir(parents=True)
    shutil.copyfile("content/technical/2026-10-31.json", root / "content/technical/2026-10-31.json")
    return root


def test_unchanged_inputs_do_not_build_or_fetch_weather(daily_data, monkeypatch, tmp_path):
    (daily_data / "public.release.json").write_text(
        json.dumps({"source_data_sha256": data_digest(daily_data)})
    )
    monkeypatch.setattr("replicantpravda.daily_build.build", lambda *a, **k: pytest.fail("build"))
    assert prepare(daily_data, tmp_path / "out")["changed"] is False


def test_stale_data_do_not_publish_yesterday(daily_data, tmp_path):
    result = prepare(daily_data, tmp_path / "out", today=date(2026, 11, 1))
    assert result["changed"] is False
    assert result["reason"] == "Waiting for today's data"


def test_all_twelve_dates_required(daily_data, tmp_path):
    path = daily_data / "data/latest/business/en.json"
    data = json.loads(path.read_text())
    data.update(issue_date="2026-10-30", issue_id="daily-2026-10-30")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="twelve feeds"):
        prepare(daily_data, tmp_path / "out", today=date(2026, 10, 31))


def test_history_prefers_published_audience_sources_and_ignores_revisions(daily_data):
    source = daily_data / "content/technical/2026-10-31.json"
    data = json.loads(source.read_text())
    data["revision"] = 17
    target = daily_data / "content/editions/engineer/2026-10-31.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data))
    revisions = source.parent / "revisions"
    revisions.mkdir()
    (revisions / "2026-10-31-r1.json").write_text("not an issue")
    history = load_history(daily_data)
    assert history["engineer", date(2026, 10, 31)].revision == 17


def test_failed_build_cannot_commit_or_push(tmp_path, monkeypatch):
    runner = load_script("daily_publish")
    state = tmp_path / "state"
    (state / "app").mkdir(parents=True)
    calls = []

    def fake(command, cwd, **kwargs):
        calls.append(command)
        if command[:4] == ["git", "remote", "get-url", "origin"]:
            return runner.REPOSITORY
        if "replicantpravda.daily_build" in command:
            raise ValueError("Invalid layout")
        return ""

    monkeypatch.setattr(runner, "run", fake)
    with pytest.raises(ValueError, match="layout"):
        runner.publish(state, push=True)
    assert not any("commit" in command or "push" in command for command in calls)


@pytest.mark.parametrize("next_day", [False, True])
def test_daily_numbering_revision_and_complete_publication(
    daily_data, tmp_path, monkeypatch, next_day
):
    from replicantpravda.render import load_issue

    template = load_issue(daily_data / "content/technical/2026-10-31.json")
    target_day = date(2026, 11, 1) if next_day else template.issue_id
    if next_day:
        for path in (daily_data / "data/latest").glob("*/*.json"):
            data = json.loads(path.read_text())
            data.update(issue_date=str(target_day), issue_id=f"daily-{target_day}")
            path.write_text(json.dumps(data))
    (daily_data / "public.release.json").write_text(
        json.dumps({"issues": [{"issue_id": str(template.issue_id)}]})
    )
    forecasts = []

    def forecast(day, location):
        forecasts.append(location)
        previous = (
            template.weather
            if location == "ichikawa"
            else next(
                edition.weather
                for edition in template.languages.values()
                if edition.weather and edition.weather.location == location
            )
        )
        return previous.model_copy(update={"forecast_date": day})

    def build(issue, snapshot, **kwargs):
        assert issue.number == (4 if next_day else 3)
        assert issue.revision == (1 if next_day else template.revision + 1)
        assert kwargs["publication"] is True and kwargs["pdf"] is True
        assert {i.edition for i in kwargs["reader_issues"]} == {
            "business",
            "enthusiast",
            "children",
        }
        snapshot.mkdir(parents=True)

    def release(snapshot, public):
        public.mkdir()
        public.with_name("public.release.json").write_text("{}")

    monkeypatch.setattr("replicantpravda.daily_build.fetch_forecast", forecast)
    monkeypatch.setattr("replicantpravda.daily_build.build", build)
    monkeypatch.setattr("replicantpravda.daily_build.prepare_release", release)
    result = prepare(daily_data, tmp_path / "run", today=target_day)
    assert result["changed"] is True
    assert len(forecasts) == (3 if next_day else 0)
    assert len(list((daily_data / "content/editions").glob(f"*/{target_day}.json"))) == 4
