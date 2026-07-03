"""Fetch and parse Google Maps Platform Weather forecasts; pure helpers.

parse_hourly() returns a list of dicts, each with keys:
    hour, ampm_label, is_daytime, condition, icon_uri, temp_f, feels_f,
    pop, precip_type, thunder, uv
parse_daily() returns a list of dicts, each with keys:
    name, icon_uri, hi_f, lo_f, day, night
    where day/night are dicts with keys: pop, precip_type, qpf_mm, thunder
"""

import datetime
import json
import os
from urllib.parse import urlencode

import requests

_DRY_POP_THRESHOLD = 5


def c_to_f(celsius):
    """Convert Celsius to Fahrenheit, rounded to the nearest int."""
    return round(celsius * 9 / 5 + 32)


def hour_label(hour):
    """Format a 0-23 hour as a compact label like '12A', '6A', '3P'."""
    suffix = "A" if hour < 12 else "P"
    h12 = hour % 12
    if h12 == 0:
        h12 = 12
    return "{}{}".format(h12, suffix)


def intensity_level(qpf_mm, pop):
    """Map precip amount (mm) to pip level 0-3.

    0 = none/dry, 1 = light (<2.5mm), 2 = moderate (2.5-7.5mm), 3 = heavy (>7.5mm).
    Returns 0 when there is effectively no precip chance or no accumulation.
    """
    if pop < _DRY_POP_THRESHOLD or qpf_mm <= 0:
        return 0
    if qpf_mm < 2.5:
        return 1
    if qpf_mm < 7.5:
        return 2
    return 3


def precip_kind(pop, precip_type, thunder):
    """Classify a precip cell into a semantic kind for coloring.

    Returns one of: 'dry', 'storm', 'snow', 'mix', 'rain'.
    Thunderstorm dominance (>=30%) takes priority over type.
    """
    if pop < _DRY_POP_THRESHOLD:
        return "dry"
    if thunder >= 30:
        return "storm"
    if precip_type == "SNOW":
        return "snow"
    if precip_type in ("SLEET", "ICE", "FREEZING_RAIN"):
        return "mix"
    return "rain"


_HOURLY_ENDPOINT = "https://weather.googleapis.com/v1/forecast/hours:lookup"
_DAILY_ENDPOINT = "https://weather.googleapis.com/v1/forecast/days:lookup"


def hourly_url(lat, long, key, hours=12):
    params = {"key": key, "location.latitude": lat, "location.longitude": long,
              "hours": hours, "unitsSystem": "METRIC"}
    return "{}?{}".format(_HOURLY_ENDPOINT, urlencode(params))


def daily_url(lat, long, key, days=10):
    params = {"key": key, "location.latitude": lat, "location.longitude": long,
              "days": days, "unitsSystem": "METRIC"}
    return "{}?{}".format(_DAILY_ENDPOINT, urlencode(params))


class WeatherAPIError(Exception):
    """Raised on a non-OK Weather API response, carrying the API's own message."""


def _raise_for_api_error(resp):
    """Raise WeatherAPIError with the API's own error text on a non-OK response.

    Google returns a JSON body like {"error": {"message": "..."}} on 4xx/5xx.
    Surfacing that message (rather than requests' generic "400 Client Error")
    makes failures actionable on the error card and in the cron log.
    """
    if resp.ok:
        return
    try:
        detail = resp.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    if not detail:
        detail = (getattr(resp, "text", "") or getattr(resp, "reason", "") or "").strip()[:200]
    raise WeatherAPIError("Weather API {} error: {}".format(resp.status_code, detail))


def fetch_live(lat, long, key, hours=12, days=10, timeout=20):
    """Fetch and parse both forecasts from the live API. Returns (hours, days)."""
    hourly_resp = requests.get(hourly_url(lat, long, key, hours), timeout=timeout)
    _raise_for_api_error(hourly_resp)
    daily_resp = requests.get(daily_url(lat, long, key, days), timeout=timeout)
    _raise_for_api_error(daily_resp)
    return (
        parse_hourly(hourly_resp.json(), count=hours),
        parse_daily(daily_resp.json(), count=days),
    )


def load_from_fixtures(fixture_dir, hours=12, days=10):
    """Load and parse both forecasts from local fixture files. Returns (hours, days)."""
    with open(os.path.join(fixture_dir, "hourly_response.json")) as f:
        hourly = json.load(f)
    with open(os.path.join(fixture_dir, "daily_response.json")) as f:
        daily = json.load(f)
    return parse_hourly(hourly, count=hours), parse_daily(daily, count=days)


_WEEKDAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _day_name(display_date):
    """Return a 3-letter weekday from a Google displayDate dict, or '' if missing."""
    if not display_date:
        return ""
    d = datetime.date(display_date["year"], display_date["month"], display_date["day"])
    return _WEEKDAY[d.weekday()]


def _parse_precip_block(block):
    """Extract precip fields from a daytimeForecast/nighttimeForecast object."""
    precip = block.get("precipitation", {})
    prob = precip.get("probability", {})
    return {
        "pop": prob.get("percent", 0),
        "precip_type": prob.get("type", "RAIN"),
        "qpf_mm": precip.get("qpf", {}).get("quantity", 0.0),
        "thunder": block.get("thunderstormProbability", 0),
    }


def parse_daily(data, count=10):
    """Extract the first `count` days from a Google daily response.

    Returns a list of dicts (see module docstring for shape).
    """
    days = []
    for obj in data.get("forecastDays", [])[:count]:
        day_block = obj.get("daytimeForecast", {})
        night_block = obj.get("nighttimeForecast", {})
        cond = day_block.get("weatherCondition", {})
        days.append({
            "name": _day_name(obj.get("displayDate", {})),
            "icon_uri": cond.get("iconBaseUri", ""),
            "hi_f": c_to_f(obj.get("maxTemperature", {}).get("degrees", 0)),
            "lo_f": c_to_f(obj.get("minTemperature", {}).get("degrees", 0)),
            "day": _parse_precip_block(day_block),
            "night": _parse_precip_block(night_block),
        })
    return days


def parse_hourly(data, count=12):
    """Extract the first `count` hours from a Google hourly response.

    Returns a list of dicts (see module docstring for shape).
    """
    hours = []
    for obj in data.get("forecastHours", [])[:count]:
        cond = obj.get("weatherCondition", {})
        precip = obj.get("precipitation", {})
        prob = precip.get("probability", {})
        hour = obj.get("displayDateTime", {}).get("hours", 0)
        hours.append({
            "hour": hour,
            "ampm_label": hour_label(hour),
            "is_daytime": obj.get("isDaytime", True),
            "condition": cond.get("type", "UNKNOWN"),
            "icon_uri": cond.get("iconBaseUri", ""),
            "temp_f": c_to_f(obj.get("temperature", {}).get("degrees", 0)),
            "feels_f": c_to_f(obj.get("feelsLikeTemperature", {}).get("degrees", 0)),
            "pop": prob.get("percent", 0),
            "precip_type": prob.get("type", "RAIN"),
            "thunder": obj.get("thunderstormProbability", 0),
            "uv": obj.get("uvIndex", 0),
        })
    return hours


_ENSEMBLE_ENDPOINT = "https://ensemble-api.open-meteo.com/v1/ensemble"


def percentile(sorted_vals, p):
    """Linear-interpolated percentile (p in 0..100) of a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _align_index(times, first_hour):
    """Index of the first entry whose local hour == first_hour (else 0)."""
    for i, t in enumerate(times):
        if int(t[11:13]) == first_hour:
            return i
    return 0


def parse_ensemble(data, first_hour, count=12):
    """Return (bands, gust): per-hour temp (p10,p25,p75,p90) and mean gust mph."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return [], []
    start = _align_index(times, first_hour)
    temp_keys = [k for k in hourly if k.startswith("temperature_2m")]
    gust_keys = [k for k in hourly if k.startswith("wind_gusts_10m")]
    bands, gust = [], []
    for i in range(start, min(start + count, len(times))):
        temps = sorted(hourly[k][i] for k in temp_keys
                       if i < len(hourly[k]) and hourly[k][i] is not None)
        bands.append((round(percentile(temps, 10)), round(percentile(temps, 25)),
                      round(percentile(temps, 75)), round(percentile(temps, 90))))
        gs = [hourly[k][i] for k in gust_keys
              if i < len(hourly[k]) and hourly[k][i] is not None]
        gust.append(round(sum(gs) / len(gs)) if gs else 0)
    return bands, gust


def ensemble_url(lat, long, count=12):
    params = {"latitude": lat, "longitude": long, "models": "gfs_seamless",
              "hourly": "temperature_2m,wind_gusts_10m",
              "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
              "timezone": "auto", "forecast_days": 2}
    return "{}?{}".format(_ENSEMBLE_ENDPOINT, urlencode(params))


def fetch_ensemble(lat, long, first_hour, count=12, timeout=20):
    resp = requests.get(ensemble_url(lat, long, count), timeout=timeout)
    resp.raise_for_status()
    return parse_ensemble(resp.json(), first_hour, count)


def load_ensemble_fixture(fixture_dir, first_hour, count=12):
    with open(os.path.join(fixture_dir, "openmeteo_ensemble.json")) as f:
        return parse_ensemble(json.load(f), first_hour, count)


_AIRQUALITY_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"
_FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def parse_air_quality(data, first_hour, count=12):
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    aqi = hourly.get("us_aqi", [])
    if not times:
        return []
    start = _align_index(times, first_hour)
    out = []
    for i in range(start, min(start + count, len(times))):
        v = aqi[i] if i < len(aqi) and aqi[i] is not None else 0
        out.append(int(v))
    return out


def air_quality_url(lat, long):
    params = {"latitude": lat, "longitude": long, "hourly": "us_aqi",
              "timezone": "auto", "forecast_days": 2}
    return "{}?{}".format(_AIRQUALITY_ENDPOINT, urlencode(params))


def fetch_air_quality(lat, long, first_hour, count=12, timeout=20):
    resp = requests.get(air_quality_url(lat, long), timeout=timeout)
    resp.raise_for_status()
    return parse_air_quality(resp.json(), first_hour, count)


def load_airquality_fixture(fixture_dir, first_hour, count=12):
    with open(os.path.join(fixture_dir, "openmeteo_airquality.json")) as f:
        return parse_air_quality(json.load(f), first_hour, count)


def _sun_label(iso):
    hour = int(iso[11:13])
    suffix = "a" if hour < 12 else "p"
    h12 = hour % 12 or 12
    return "{}{}".format(h12, suffix)


def parse_sun(data):
    daily = data.get("daily", {})
    rise = daily.get("sunrise") or []
    setl = daily.get("sunset") or []
    return {"sunrise": _sun_label(rise[0]) if rise else None,
            "sunset": _sun_label(setl[0]) if setl else None}


def sun_url(lat, long):
    params = {"latitude": lat, "longitude": long, "daily": "sunrise,sunset",
              "timezone": "auto", "forecast_days": 1}
    return "{}?{}".format(_FORECAST_ENDPOINT, urlencode(params))


def fetch_sun(lat, long, timeout=20):
    resp = requests.get(sun_url(lat, long), timeout=timeout)
    resp.raise_for_status()
    return parse_sun(resp.json())
