"""Fetch and parse Google Maps Platform Weather forecasts; pure helpers."""

import datetime
import json
import os
import requests


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
    if pop < 5 or qpf_mm <= 0:
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
    if pop < 5:
        return "dry"
    if thunder >= 30:
        return "storm"
    if precip_type == "SNOW":
        return "snow"
    if precip_type in ("SLEET", "ICE", "FREEZING_RAIN"):
        return "mix"
    return "rain"


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
