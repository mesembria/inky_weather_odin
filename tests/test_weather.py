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


def test_hour_label_midnight():
    assert weather.hour_label(0) == "12A"


def test_hour_label_noon():
    assert weather.hour_label(12) == "12P"


def test_hour_label_morning():
    assert weather.hour_label(6) == "6A"


def test_hour_label_evening():
    assert weather.hour_label(15) == "3P"


def test_intensity_dry_when_no_pop():
    assert weather.intensity_level(qpf_mm=5.0, pop=0) == 0


def test_intensity_dry_when_no_qpf():
    assert weather.intensity_level(qpf_mm=0.0, pop=80) == 0


def test_intensity_light():
    assert weather.intensity_level(qpf_mm=1.0, pop=60) == 1


def test_intensity_moderate():
    assert weather.intensity_level(qpf_mm=5.0, pop=80) == 2


def test_intensity_heavy():
    assert weather.intensity_level(qpf_mm=12.0, pop=90) == 3
