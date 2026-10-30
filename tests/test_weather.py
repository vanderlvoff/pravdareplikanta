"""Offline forecast adapter, validation, CLI and localized output checks."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from replicantpravda.cli import main
from replicantpravda.models import Issue
from replicantpravda.render import build
from replicantpravda.weather import Weather, condition, parse_forecast

DAY = date(2026, 10, 29)
RETRIEVED = datetime(2026, 10, 28, 22, tzinfo=UTC)


@pytest.fixture
def payload():
    return json.loads(Path("tests/fixtures/open_meteo.json").read_text())


def test_forecast_adapter(payload):
    weather = parse_forecast(payload, DAY, RETRIEVED)
    assert weather.timezone == "Asia/Tokyo"
    assert [s.hour for s in weather.slots] == [9, 12, 18]
    assert [s.condition for s in weather.slots] == ["clear", "cloudy", "rain"]
    assert weather.slots[0].wind_speed_ms == 3
    assert weather.retrieved_at == RETRIEVED
    assert weather.source_name == "Open-Meteo"


@pytest.mark.parametrize("fault", ["missing_hour", "null", "units", "timezone", "code"])
def test_bad_provider_data(payload, fault):
    if fault == "missing_hour":
        payload["hourly"]["time"][0] = "2026-10-29T08:00"
    elif fault == "null":
        payload["hourly"]["temperature_2m"][0] = None
    elif fault == "units":
        payload["hourly_units"]["wind_speed_10m"] = "km/h"
    elif fault == "timezone":
        payload["timezone"] = "UTC"
    else:
        payload["hourly"]["weather_code"][0] = 999
    with pytest.raises(ValueError):
        parse_forecast(payload, DAY, RETRIEVED)


@pytest.mark.parametrize("fault", ["probability", "order", "range", "naive_time", "nonfinite"])
def test_invalid_snapshot(payload, fault):
    data = parse_forecast(payload, DAY, RETRIEVED).model_dump(mode="json")
    if fault == "probability":
        data["slots"][0]["precipitation_probability"] = 101
    elif fault == "order":
        data["slots"].reverse()
    elif fault == "range":
        data["temperature_max_c"] = 0
    elif fault == "naive_time":
        data["retrieved_at"] = "2026-10-29T06:45:00"
    else:
        data["slots"][0]["wind_speed_ms"] = float("nan")
    with pytest.raises(ValidationError):
        Weather.model_validate(data)


def test_weather_date_matches_issue(payload):
    data = json.loads(Path("content/issues/2026-10-29.json").read_text())
    weather = parse_forecast(payload, DAY, RETRIEVED).model_dump(mode="json")
    weather["forecast_date"] = "2026-10-30"
    data["weather"] = weather
    with pytest.raises(ValidationError, match="Weather date"):
        Issue.model_validate(data)


def test_localized_weather_and_demo_label(payload, tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Build must not use network")

    monkeypatch.setattr("replicantpravda.weather.urlopen", no_network)
    data = json.loads(Path("content/issues/2026-10-29.json").read_text())
    data["weather"] = parse_forecast(payload, DAY, RETRIEVED).model_dump(mode="json")
    build(Issue.model_validate(data), tmp_path / "forecast")
    for lang, city in (("ru", "ИТИКАВА"), ("en", "ICHIKAWA"), ("ja", "市川")):
        html = (tmp_path / "forecast" / lang / "index.html").read_text()
        assert city in html
        assert html.count('class="weather-slot"') == 3
        assert "09:00" in html and "12:00" in html and "18:00" in html
        assert "Open-Meteo" in html
        assert 'class="weather-demo"' not in html
    data["weather"]["kind"] = "demo"
    data["weather"]["source_name"] = "Editorial fixture"
    build(Issue.model_validate(data), tmp_path / "demo")
    assert 'class="weather-demo"' in (tmp_path / "demo/ru/index.html").read_text()


def test_weather_cli_snapshot_and_no_overwrite(payload, monkeypatch, tmp_path):
    weather = parse_forecast(payload, DAY, RETRIEVED)
    monkeypatch.setattr("replicantpravda.cli.fetch_forecast", lambda day: copy.deepcopy(weather))
    output = tmp_path / "forecast.json"
    monkeypatch.setattr("sys.argv", ["rp", "weather", "--date", str(DAY), "--output", str(output)])
    assert main() == 0
    before = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert output.read_bytes() == before
    monkeypatch.setattr(
        "sys.argv",
        [
            "rp",
            "build",
            "--issue",
            str(DAY),
            "--weather",
            str(output),
            "--output",
            str(tmp_path / "site"),
        ],
    )
    assert main() == 0


def test_weather_code_mapping():
    assert condition(97) == "storm"
    assert condition(85) == "snow"
    assert condition(45) == "fog"


def test_network_failure_keeps_snapshot_absent(monkeypatch, tmp_path):
    from urllib.error import URLError

    def unavailable(day):
        raise URLError("offline")

    output = tmp_path / "missing.json"
    monkeypatch.setattr("replicantpravda.cli.fetch_forecast", unavailable)
    monkeypatch.setattr("sys.argv", ["rp", "weather", "--date", str(DAY), "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert not output.exists()


def test_missing_weather_is_explicit(tmp_path):
    data = json.loads(Path("content/issues/2026-10-29.json").read_text())
    del data["weather"]
    build(Issue.model_validate(data), tmp_path / "site")
    html = (tmp_path / "site/ru/index.html").read_text()
    assert "Прогноз для выпуска не предоставлен" in html
    assert 'class="weather-slot"' not in html


@pytest.mark.parametrize(
    "location,timezone", [("breukelen", "Europe/Amsterdam"), ("smolensk", "Europe/Moscow")]
)
def test_location_specific_forecasts(payload, location, timezone):
    payload["timezone"] = timezone
    weather = parse_forecast(payload, DAY, RETRIEVED, location)
    assert weather.location == location and weather.timezone == timezone
    assert timezone.replace("/", "%2F") in str(weather.source_url)
    bad = weather.model_dump()
    bad["timezone"] = "Asia/Tokyo"
    with pytest.raises(ValidationError, match="timezone"):
        Weather.model_validate(bad)


def test_edition_weather_uses_local_city_time_and_source(payload, tmp_path):
    data = json.loads(Path("content/issues/2026-10-29.json").read_text())
    for language, location, timezone in (
        ("en", "breukelen", "Europe/Amsterdam"),
        ("ja", "smolensk", "Europe/Moscow"),
    ):
        local = copy.deepcopy(payload)
        local["timezone"] = timezone
        data["languages"][language]["weather"] = parse_forecast(
            local, DAY, RETRIEVED, location
        ).model_dump(mode="json")
    build(Issue.model_validate(data), tmp_path / "site")
    for lang, city, zone in (
        ("en", "Breukelen", "CET"),
        ("ja", "スモレンスク", "MSK"),
    ):
        html = (tmp_path / "site" / lang / "index.html").read_text()
        assert city in html and f" · {zone}</p>" in html
        assert "JST" not in html
    data["languages"]["en"]["weather"]["forecast_date"] = "2026-10-30"
    with pytest.raises(ValidationError, match="Edition weather date"):
        Issue.model_validate(data)
