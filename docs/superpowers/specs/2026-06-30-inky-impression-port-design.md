# Inky Impression 7.3" Weather Display — Design

**Date:** 2026-06-30
**Status:** Approved design, ready for implementation planning

## Overview

Port the MagTag "Odin" weather display to a Raspberry Pi + Pimoroni Inky
Impression 7.3" (800×480, 7-color ACeP e-ink), and expand it to take advantage
of the larger, color canvas.

The existing MagTag app (`code.py`) fetches hourly forecasts from the Google
Maps Platform Weather API and renders a 9-column hourly view on a 296×128
grayscale display, then deep-sleeps. This project reimplements the same idea for
a much larger color display with substantially richer content: a 12-hour hourly
panel plus a 10-day forecast strip.

This is a rewrite, not a line-by-line port. The data-fetch and field-extraction
logic ports closely; the entire display layer is new (CircuitPython `displayio`
→ Python 3 + Pillow).

## Goals

- Fetch hourly + daily forecasts from the Google Maps Platform Weather API.
- Render an 800×480 color image and push it to the Inky Impression.
- Show the next 12 hours (rolling window) at 1-hour resolution.
- Show a 10-day forecast with a temperature-spread bar and clear precipitation
  detail that distinguishes popup thunderstorms, definite rain, and overnight
  rain at a glance.
- Run unattended on a Raspberry Pi, refreshing hourly via cron.
- Be developable and testable on a Mac without a Pi or display attached.

## Non-Goals

- Battery operation / deep-sleep power management (Pi is wall-powered).
- Integrating the user's personal weather station (forecast-only display).
- Geocoding place names (location is configured as lat/long + a display label).
- Touch or button interaction.

## Platform & Stack

| Concern | MagTag (current) | Inky (new) |
|---|---|---|
| Board | Adafruit MagTag (ESP32-S2) | Raspberry Pi 4 (dev) → Pi Zero 2W (final) |
| Runtime | CircuitPython | Python 3 |
| Display | 296×128 grayscale | 800×480 7-color ACeP |
| Draw lib | `displayio` | Pillow (PIL) |
| HTTP | `magtag.network.fetch()` | `requests` |
| Scheduling | `alarm` deep-sleep | cron (`0 * * * *`) |
| Display driver | built into MagTag lib | Pimoroni `inky` |

The Inky Impression 7.3" is a HAT that mounts on the Pi's 40-pin GPIO header;
the Pi is supplied separately. Development happens on the Pi 4; the final
install targets a Pi Zero 2W (with pre-soldered header) for low power draw and
compact mounting.

## Architecture

Single Python script, linear execution, triggered hourly by cron:

1. **Fetch** — two API calls:
   - Hourly forecast (up to 240h available; take the first 12 from now).
   - Daily forecast (10 days).
   Both use the same Google Maps Platform API key.
2. **Format** — extract and convert fields into simple dicts/dataclasses.
   Celsius → Fahrenheit; scale/normalize as needed.
3. **Render** — Pillow builds an 800×480 `Image` in the Inky 7-color palette.
4. **Push** — the `inky` library sends the image to the display.

No event loop, no persistent process; cron restarts the script each hour, which
naturally matches the rolling 12-hour hourly window.

### Module layout (proposed)

- `weather.py` — API fetch + parse (hourly and daily), unit conversion,
  icon mapping, intensity/threshold helpers. Pure functions, no I/O beyond the
  fetch itself. Unit-testable.
- `render.py` — Pillow drawing functions that take formatted data and produce
  the `Image`. Pure (data in, image out). Unit-/snapshot-testable.
- `main.py` — orchestration: load config, fetch, format, render, push, handle
  errors. The only module that touches the network and the display.
- `config.py` / `config.example.py` — credentials and location (see below).

## Configuration

A Python config module (mirroring the current `secrets.py` pattern), never
committed with real values:

```python
config = {
    'google_weather_key': '...',      # Google Maps Platform Weather API key
    'lat': '37.21350',
    'long': '-80.03739',
    'location_name': 'Blacksburg, VA', # header label; optional
}
```

- The app uses `lat`/`long` for the API calls.
- `location_name` is used only for the header text. If omitted, the header
  location slot is left blank (or falls back to coordinates).
- No geocoding — the label is maintained manually since location rarely changes.

## Layout

800×480, split into a left **hourly panel** (~585px) and a right **daily strip**
(~215px), separated by a vertical rule. A header bar spans the top.

### Header (full width, ~30px)

```
Blacksburg, VA · Tue Jun 30        Updated 10:02 AM        10-DAY FORECAST
```

- **Left:** location name · abbreviated date.
- **Center:** last-updated time.
- **Right:** "10-DAY FORECAST" label over the daily strip.

### Hourly panel (left, next 12 hours, rolling)

The window is always "the next 12 hours from now" — at 2pm it shows 2pm–1am; the
hourly cron refresh keeps it current. 12 columns, one per hour. Vertical zones,
top to bottom:

1. **Temperature graph** (~250px) — each hour's weather icon positioned
   vertically by temperature relative to the 12-hour min/max (warmer = higher),
   with the temperature value labeled below each icon. Ported from the MagTag
   `build_temp_group()` approach.
2. **Feels-like row** (~18px) — "FL 73°" per hour.
3. **Precipitation bars** (~80px) — vertical bars scaled by precip probability;
   blue for rain, orange when thunderstorm probability > 30% (with a ⚡ marker
   above the bar), percentage labeled in the bar.
4. **UV index row** (~22px) — "UV 5" per hour, color-graded (green→amber→red),
   bold when ≥ 6.
5. **Hour labels** (~30px) — "10A", "2P", etc.

Night hours (from `isDaytime: false`) get a subtle blue tint overlay across the
full panel height.

### Daily strip (right, 10 days)

One row per day (~45px). Each row:

1. **Icon + day name** (left column).
2. **Temperature spread bar** — a horizontal bar showing the day's low→high
   range plotted against a **shared 10-day scale** (the coldest low and warmest
   high across all 10 days), so spreads and week-over-week shifts are directly
   comparable. The bar's fill graduates blue (cool) → red (warm). Low/high
   values labeled inline at the bar ends.
3. **Stacked Day / Night precipitation bars** — two horizontal fill bars, **D**
   (daytime, 7am–7pm) above **N** (nighttime, 7pm–7am):
   - **Fill length** = precipitation probability (%).
   - **Color** = precipitation type: blue rain, orange thunderstorm, cyan snow,
     purple wintry mix.
   - **⚡ marker** trailing the bar when thunderstorm probability ≥ 30%.
   - **Intensity pips** (● / ●● / ●●●) trailing the bar, from QPF quantity:
     light < 2.5mm, moderate 2.5–7.5mm, heavy > 7.5mm.

This encoding gives each precipitation scenario a distinct visual signature:

| Scenario | Data fingerprint | Visual signature |
|---|---|---|
| Popup PM thunderstorm | daytime thunderstorm ≥ 30%, moderate PoP, low QPF | short **orange** D bar with **⚡**, tiny N bar |
| Definite rain | high PoP, low thunderstorm, high QPF | both bars nearly full, ●●● pips |
| Overnight rain | nighttime PoP ≫ daytime PoP | stub D bar, long **blue** N bar |

The three channels — probability (length), type (color), intensity (pips) — are
orthogonal, so none is confused with another.

## Data

### Hourly (one API call; use first 12 of `forecastHours`)

| Field | Source |
|---|---|
| Local hour | `displayDateTime.hours` (already local) |
| Is daytime | `isDaytime` |
| Condition type | `weatherCondition.type` |
| Temperature °F | `temperature.degrees` × 9/5 + 32 |
| Feels-like °F | `feelsLikeTemperature.degrees` × 9/5 + 32 |
| Precip probability | `precipitation.probability.percent` |
| Precip type | `precipitation.probability.type` |
| Thunderstorm % | `thunderstormProbability` |
| UV index | `uvIndex` |

### Daily (separate API call; 10 days from `forecastDays`)

The daily endpoint provides **separate `daytimeForecast` and `nighttimeForecast`
objects**, each with its own precipitation probability, type, and QPF — which is
what enables the D/N split.

| Field | Source |
|---|---|
| Day name | derived from `interval.startTime` |
| Condition (icon) | `daytimeForecast.weatherCondition.type` |
| High °F | `maxTemperature.degrees` × 9/5 + 32 |
| Low °F | `minTemperature.degrees` × 9/5 + 32 |
| Day precip prob | `daytimeForecast.precipitation.probability.percent` |
| Day precip type | `daytimeForecast.precipitation.probability.type` |
| Day QPF | `daytimeForecast.precipitation.qpf.quantity` (mm) |
| Day thunderstorm % | `daytimeForecast.thunderstormProbability` |
| Night precip prob | `nighttimeForecast.precipitation.probability.percent` |
| Night precip type | `nighttimeForecast.precipitation.probability.type` |
| Night QPF | `nighttimeForecast.precipitation.qpf.quantity` (mm) |
| Night thunderstorm % | `nighttimeForecast.thunderstormProbability` |

### API usage

Hourly cron refresh = 24 calls/day × 2 endpoints = ~1,440 calls/month, well
within the Google Maps Platform free tier (10,000 calls/month).

## Icons

The MagTag's 20×20px grayscale BMP sprite sheet is too small to scale up cleanly
on this canvas. A new, larger PNG sprite sheet (or individual PNGs) will be
drawn/sourced at an appropriate size for the 800×480 display, in the Inky color
palette. `ICON_MAP` (Google `weatherCondition.type` → tile/asset) ports over
from the existing Google Weather work; day/night variants continue to dispatch
on `isDaytime`.

## Error Handling

- **Offline / development mode:** a `--fixture` flag loads a saved JSON response
  (continuing the existing `google_response.txt` pattern) instead of hitting the
  API, and writes the rendered PNG to a file. This allows full layout iteration
  on a Mac with no Pi and no display.
- **Runtime failures:** on network/API/parse error, render an error card to the
  display (analogous to the MagTag `show_error()`), rather than crashing
  silently or leaving a stale screen with no indication. Cron retries next hour.
- Targeted handling around each external failure point (network, JSON parse,
  empty forecast arrays), following the pattern already established in the
  MagTag error-handling work.

## Testing

Because rendering is now pure Python producing a Pillow image (rather than
CircuitPython `displayio` on-device), the logic is unit-testable with pytest:

- Unit tests for `weather.py`: °C→°F conversion, icon mapping, day/night
  classification, intensity pip thresholds, precip-type → color mapping,
  rolling-window selection.
- Snapshot/smoke test for `render.py`: render a known fixture to an image and
  assert dimensions/palette (and optionally compare against a reference PNG).
- The `--fixture` path doubles as an integration smoke test.

## Deployment

- Copy the app to the Pi; store real credentials in `config.py`.
- Install dependencies: `inky`, `Pillow`, `requests` (via `pip`, in a venv).
- Add a cron entry: `0 * * * *` runs `main.py` at the top of every hour.
- No build step; no on-device compilation.

## Open Questions / Future Enhancements

- Optional: reverse-geocode lat/long to auto-populate `location_name` (deferred;
  manual label chosen for simplicity).
- Optional: a "now" anchor comparing the user's personal weather-station reading
  against the forecast (explicitly out of scope for this version).
