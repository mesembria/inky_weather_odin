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
