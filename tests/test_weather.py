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


def test_precip_kind_dry():
    assert weather.precip_kind(pop=0, precip_type="RAIN", thunder=0) == "dry"


def test_precip_kind_thunderstorm_takes_priority():
    assert weather.precip_kind(pop=60, precip_type="RAIN", thunder=40) == "storm"


def test_precip_kind_snow():
    assert weather.precip_kind(pop=70, precip_type="SNOW", thunder=0) == "snow"


def test_precip_kind_rain():
    assert weather.precip_kind(pop=80, precip_type="RAIN", thunder=10) == "rain"


def test_precip_kind_wintry_mix():
    assert weather.precip_kind(pop=50, precip_type="SLEET", thunder=0) == "mix"


def test_parse_hourly_returns_twelve():
    data = _load_fixture("hourly_response.json")
    hours = weather.parse_hourly(data, count=12)
    assert len(hours) == 12


def test_parse_hourly_first_hour_fields():
    data = _load_fixture("hourly_response.json")
    first = weather.parse_hourly(data, count=12)[0]
    assert first["temp_f"] == 76
    assert first["feels_f"] == 77
    assert first["condition"] == "PARTLY_CLOUDY"
    assert first["pop"] == 20
    assert first["precip_type"] == "RAIN"
    assert first["thunder"] == 0
    assert first["uv"] == 6
    assert first["is_daytime"] is True
    assert first["ampm_label"] == "10A"
    assert first["icon_uri"].endswith("/partly_cloudy")


def test_parse_hourly_handles_short_list():
    data = {"forecastHours": _load_fixture("hourly_response.json")["forecastHours"][:3]}
    hours = weather.parse_hourly(data, count=12)
    assert len(hours) == 3


def test_parse_daily_returns_ten():
    data = _load_fixture("daily_response.json")
    days = weather.parse_daily(data, count=10)
    assert len(days) == 10


def test_parse_daily_first_day_fields():
    data = _load_fixture("daily_response.json")
    first = weather.parse_daily(data, count=10)[0]
    assert first["name"] == "TUE"
    assert first["hi_f"] == 84
    assert first["lo_f"] == 60
    assert first["day"]["pop"] == 50
    assert first["day"]["thunder"] == 55
    assert first["day"]["qpf_mm"] == 2.0
    assert first["night"]["pop"] == 10
    assert first["icon_uri"].endswith("/thunderstorm")


def test_parse_daily_snow_day():
    data = _load_fixture("daily_response.json")
    days = weather.parse_daily(data, count=10)
    snow_day = days[7]
    assert snow_day["day"]["precip_type"] == "SNOW"
    assert snow_day["hi_f"] == 33


def test_hourly_url_contains_params():
    url = weather.hourly_url(lat="37.2", long="-80.0", key="ABC", hours=12)
    assert "location.latitude=37.2" in url
    assert "location.longitude=-80.0" in url
    assert "hours=12" in url
    assert "key=ABC" in url


def test_daily_url_contains_params():
    url = weather.daily_url(lat="37.2", long="-80.0", key="ABC", days=10)
    assert "days=10" in url
    assert "key=ABC" in url


def test_load_fixtures_returns_parsed():
    hours, days = weather.load_from_fixtures(FIXTURE_DIR)
    assert len(hours) == 12
    assert len(days) == 10
    assert hours[0]["temp_f"] == 76
