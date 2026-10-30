# Local weather snapshots

The issue's optional `weather` object stores the shared fallback forecast for its publication
date in the location's timezone. It includes 09:00, 12:00 and 18:00 conditions, temperatures,
precipitation probabilities, wind speed in m/s and meteorological direction in degrees.
The summary uses the provider's daily temperature range and maximum precipitation
probability, not the range of the three displayed hours.

`retrieved_at` is timezone-aware acquisition time, not model issuance time. Acquisition
can happen later than displayed hours: these remain forecast data, not observations.
The snapshot records source name and the exact request URL. Each edition uses its selected city snapshot with translated labels. The issue date must match the forecast date.

## Workflow

```sh
# Network operation, no API keys; refuses to overwrite an existing snapshot.
rp weather --date 2026-10-29 --output content/weather/2026-10-29.json

# Offline build with a saved snapshot (or omit --weather to use issue JSON data).
rp build --issue 2026-10-29 --weather content/weather/2026-10-29.json --output previews/weather-review
rp preview --output previews/weather-review
```

The forecast API only supports its available date window; an unavailable date or
network error fails without replacing a previous snapshot. Older issues must retain
their captured weather rather than fetch today's forecast. Copy approved snapshot
fields into the issue's `weather` object to keep a single canonical editorial dataset.
Do not mutate already published source without incrementing its revision.

The sample issue includes a real snapshot obtained on 2026-10-29. Tests use a separate
synthetic fixture. Manually supplied test weather must use `kind: "demo"`; the UI
marks it as demonstration data in all three languages. Missing weather is displayed
explicitly. Missing hourly fields, null values, unsupported units/codes, invalid
probabilities, invalid daily ranges and mismatched dates fail validation.

Acquisition uses the standard library with TLS certificate verification. On macOS,
if the Python installation has no default root CAs, it loads `/etc/ssl/cert.pem`.
The build never connects to a weather service, so the same JSON produces identical
HTML on repeated builds. A new request is always an explicit operator action.

Provider fields and WMO code mappings follow the [Open-Meteo documentation](https://open-meteo.com/en/docs).
Attribution and acquisition time appear in the issue footer, outside the masthead.

## Per-edition cities

Current owner settings: RU Ichikawa (Asia/Tokyo), EN Breukelen (Netherlands,
Europe/Amsterdam), JA Smolensk (Europe/Moscow). Each `languages.<lang>.weather`
overrides the shared issue weather. City labels, 09/12/18 slots and acquisition
timestamps use that snapshot's location and local timezone (including DST).
The location/timezone pair and issue date are validated; data is never relabeled
as another city's forecast. Import preserves same-date template edition weather.

```sh
rp weather --date 2026-10-30 --location breukelen --output content/weather/breukelen-2026-10-30.json
rp weather --date 2026-10-30 --location smolensk --output content/weather/smolensk-2026-10-30.json
rp build --issue 2026-10-30 --content-dir content/imported-v1.2-review --edition-weather en=content/weather/breukelen-2026-10-30.json --edition-weather ja=content/weather/smolensk-2026-10-30.json --pdf --output previews/local-weather-review
```

Existing snapshot paths refuse overwrite; use a new path for refreshes. The
combined normalized source is saved separately in `content/localized/2026-10-30.json`
(revision 4). `rp build --content-dir content/localized ...` needs no override flags.
All builds remain offline; acquisition is a separate command.
