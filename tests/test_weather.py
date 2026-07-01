import json
import os

from inky_weather import weather

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name)) as f:
        return json.load(f)


def test_c_to_f_freezing():
    assert weather.c_to_f(0) == 32


def test_c_to_f_rounds_to_int():
    assert weather.c_to_f(24.5) == 76


def test_c_to_f_negative():
    assert weather.c_to_f(-4.4) == 24
