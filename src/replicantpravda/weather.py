"""Saved Ichikawa forecast data and an explicit network acquisition adapter."""

import json
import ssl
import sys
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class WeatherRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WeatherSlot(WeatherRecord):
    hour: Literal[9, 12, 18]
    temperature_c: float = Field(ge=-90, le=60)
    condition: Literal["clear", "cloudy", "fog", "rain", "snow", "storm"]
    precipitation_probability: int = Field(ge=0, le=100)
    wind_speed_ms: float = Field(ge=0, le=150)
    wind_direction_deg: int = Field(ge=0, le=360)


class Weather(WeatherRecord):
    location: Literal["ichikawa"] = "ichikawa"
    timezone: Literal["Asia/Tokyo"] = "Asia/Tokyo"
    forecast_date: date
    retrieved_at: AwareDatetime
    kind: Literal["demo", "forecast"]
    source_name: Literal["Open-Meteo", "Editorial fixture"]
    source_url: HttpUrl
    temperature_min_c: float = Field(ge=-90, le=60)
    temperature_max_c: float = Field(ge=-90, le=60)
    precipitation_probability_max: int = Field(ge=0, le=100)
    slots: list[WeatherSlot] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def consistent(self) -> "Weather":
        if [slot.hour for slot in self.slots] != [9, 12, 18]:
            raise ValueError("Weather slots must be 09:00, 12:00, 18:00 JST in order")
        if self.temperature_min_c > self.temperature_max_c:
            raise ValueError("Weather temperature minimum exceeds maximum")
        for slot in self.slots:
            if not self.temperature_min_c <= slot.temperature_c <= self.temperature_max_c:
                raise ValueError("Hourly temperature lies outside daily range")
            if slot.precipitation_probability > self.precipitation_probability_max:
                raise ValueError("Hourly precipitation exceeds daily maximum")
        if self.kind == "forecast" and self.source_name != "Open-Meteo":
            raise ValueError("Forecast requires Open-Meteo provenance")
        return self


def condition(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 97, 99):
        return "storm"
    raise ValueError(f"Unsupported WMO weather code: {code}")


def forecast_url(day: date) -> str:
    return "https://api.open-meteo.com/v1/forecast?" + urlencode(
        {
            "latitude": 35.72,
            "longitude": 139.93,
            "timezone": "Asia/Tokyo",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "wind_speed_unit": "ms",
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,wind_direction_10m",
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
        }
    )


def parse_forecast(payload: dict, day: date, retrieved_at: datetime) -> Weather:
    """Reject incomplete provider data rather than silently inventing values."""
    try:
        if payload["timezone"] != "Asia/Tokyo":
            raise ValueError("Unexpected forecast timezone")
        hourly, daily = payload["hourly"], payload["daily"]
        expected_units = {
            "temperature_2m": "°C",
            "precipitation_probability": "%",
            "wind_speed_10m": "m/s",
            "wind_direction_10m": "°",
        }
        if any(payload["hourly_units"].get(key) != unit for key, unit in expected_units.items()):
            raise ValueError("Unexpected hourly forecast units")
        if any(
            payload["daily_units"].get(key) != unit
            for key, unit in {
                "temperature_2m_min": "°C",
                "temperature_2m_max": "°C",
                "precipitation_probability_max": "%",
            }.items()
        ):
            raise ValueError("Unexpected daily forecast units")
        if daily["time"] != [day.isoformat()]:
            raise ValueError("Unexpected forecast day")
        slots = []
        for hour in (9, 12, 18):
            index = hourly["time"].index(f"{day.isoformat()}T{hour:02}:00")
            slots.append(
                dict(
                    hour=hour,
                    temperature_c=hourly["temperature_2m"][index],
                    condition=condition(hourly["weather_code"][index]),
                    precipitation_probability=hourly["precipitation_probability"][index],
                    wind_speed_ms=hourly["wind_speed_10m"][index],
                    wind_direction_deg=hourly["wind_direction_10m"][index],
                )
            )
        return Weather(
            forecast_date=day,
            retrieved_at=retrieved_at,
            kind="forecast",
            source_name="Open-Meteo",
            source_url=forecast_url(day),
            temperature_min_c=daily["temperature_2m_min"][0],
            temperature_max_c=daily["temperature_2m_max"][0],
            precipitation_probability_max=daily["precipitation_probability_max"][0],
            slots=slots,
        )
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Incomplete forecast response") from error


def fetch_forecast(day: date) -> Weather:
    from datetime import UTC

    context = ssl.create_default_context()
    # python.org macOS installs can lack a configured default CA bundle.
    # Use the operating system CA file while retaining certificate verification.
    if sys.platform == "darwin" and not context.get_ca_certs():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    with urlopen(forecast_url(day), timeout=20, context=context) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Forecast response exceeds size limit")
        payload = json.loads(raw)
    return parse_forecast(payload, day, datetime.now(UTC))
