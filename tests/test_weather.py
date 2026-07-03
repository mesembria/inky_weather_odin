import json
import os
from unittest import mock

import pytest

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


def test_intensity_boundary_2_5_is_moderate():
    assert weather.intensity_level(qpf_mm=2.5, pop=80) == 2


def test_intensity_boundary_7_5_is_heavy():
    assert weather.intensity_level(qpf_mm=7.5, pop=80) == 3


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


def test_precip_kind_thunder_29_is_rain():
    assert weather.precip_kind(pop=60, precip_type="RAIN", thunder=29) == "rain"


def test_precip_kind_thunder_30_is_storm():
    assert weather.precip_kind(pop=60, precip_type="RAIN", thunder=30) == "storm"


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


def test_parse_daily_tolerates_missing_display_date():
    days = weather.parse_daily({"forecastDays": [{}]}, count=10)
    assert days[0]["name"] == ""


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


def test_raise_for_api_error_passes_when_ok():
    weather._raise_for_api_error(mock.Mock(ok=True))  # should not raise


def test_raise_for_api_error_uses_google_message():
    resp = mock.Mock(ok=False, status_code=400)
    resp.json.return_value = {"error": {"message": "Invalid value at 'location.longitude'"}}
    with pytest.raises(weather.WeatherAPIError) as exc:
        weather._raise_for_api_error(resp)
    assert "400" in str(exc.value)
    assert "location.longitude" in str(exc.value)


def test_raise_for_api_error_falls_back_to_text_when_no_json():
    resp = mock.Mock(ok=False, status_code=503, text="Service Unavailable",
                     reason="Service Unavailable")
    resp.json.side_effect = ValueError("no json")
    with pytest.raises(weather.WeatherAPIError) as exc:
        weather._raise_for_api_error(resp)
    assert "503" in str(exc.value)
    assert "Service Unavailable" in str(exc.value)


def test_fetch_live_raises_weather_api_error_with_message():
    resp = mock.Mock(ok=False, status_code=400)
    resp.json.return_value = {"error": {"message": "Invalid value at 'location.longitude'"}}
    with mock.patch("inky_weather.weather.requests.get", return_value=resp):
        with pytest.raises(weather.WeatherAPIError) as exc:
            weather.fetch_live("40.0", "--105.1", "KEY")
    assert "location.longitude" in str(exc.value)


def test_percentile_interpolates():
    assert weather.percentile([10, 20, 30, 40], 50) == 25


def test_parse_ensemble_aligns_and_summarizes():
    data = {"hourly": {
        "time": ["2026-07-03T12:00", "2026-07-03T13:00", "2026-07-03T14:00"],
        "temperature_2m": [70, 72, 74],
        "temperature_2m_member01": [68, 70, 72],
        "temperature_2m_member02": [74, 76, 78],
        "wind_gusts_10m": [10, 12, 14],
        "wind_gusts_10m_member01": [12, 14, 16],
    }}
    bands, gust = weather.parse_ensemble(data, first_hour=13, count=2)
    assert len(bands) == 2
    p10, p25, p75, p90 = bands[0]      # aligned to the 13:00 row
    assert p10 <= p25 <= p75 <= p90
    assert gust[0] == 13               # mean of [12, 14]
