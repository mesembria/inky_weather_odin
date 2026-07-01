"""Fetch and parse Google Maps Platform Weather forecasts; pure helpers."""

import datetime
import json
import os
import requests


def c_to_f(celsius):
    """Convert Celsius to Fahrenheit, rounded to the nearest int."""
    return round(celsius * 9 / 5 + 32)
