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
