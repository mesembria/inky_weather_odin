"""Regression: Google's forecast day runs 07:00->07:00 local.

Before 07:00 local, days:lookup returns YESTERDAY's forecast day at index 0.
Taking days[0] as "today" made the trend card describe the wrong day while the
DRESS card (built from the hourly feed) described the right one, producing the
two contradictory banners reported from the panel.
"""
import datetime

from inky_weather import advice, history, weather


def _hours(temps, start=5):
    """Hourly feed starting at `start` local, one entry per hour."""
    out = []
    for i, t in enumerate(temps):
        h = (start + i) % 24
        out.append({"hour": h, "ampm_label": weather.hour_label(h),
                    "is_daytime": 7 <= h < 19, "condition": "CLEAR",
                    "icon_uri": "", "temp_f": t, "feels_f": t, "dew_f": 45,
                    "pop": 0, "precip_type": "RAIN", "thunder": 0, "uv": 6})
    return out


def _day(date, hi, lo=55):
    return {"date": date, "name": "SUN", "icon_uri": "", "hi_f": hi, "lo_f": lo,
            "day": {"pop": 0, "precip_type": "RAIN", "qpf_mm": 0.0, "thunder": 0},
            "night": {"pop": 0, "precip_type": "RAIN", "qpf_mm": 0.0, "thunder": 0}}


def _cards(days, hours, today, hist):
    days = weather.days_from(days, today)
    trend = history.trend_input(days, hist, today)
    return advice.build_cards(hours, [], [], [], {}, today, days=days, trend=trend)


def test_pre_7am_trend_matches_the_dress_card_hot_day():
    """Reported: DRESS 'Hot 54-92' beside TREND 'Steady, today 75'."""
    today = datetime.date(2026, 9, 13)
    # 5am run: the next 12 hours climb to today's real high of 92.
    hours = _hours([54, 57, 62, 69, 76, 82, 86, 89, 91, 92, 91, 90])
    days = [_day(today - datetime.timedelta(days=1), 75),   # Google's index 0
            _day(today, 92), _day(today + datetime.timedelta(days=1), 83),
            _day(today + datetime.timedelta(days=2), 69)]
    hist = {(today - datetime.timedelta(days=1)).isoformat(): {"hi_f": 75, "lo_f": 55}}

    cards = _cards(days, hours, today, hist)
    dress = cards[0]
    trend = next(c for c in cards if c["cat"] == "TREND")

    assert dress["detail"].startswith("54-92")
    assert "92" in trend["detail"], trend                 # not yesterday's 75
    assert trend["verdict"] == "Much warmer"              # 92 vs 75, not "Steady"


def test_pre_7am_trend_does_not_label_todays_high_as_tomorrow():
    """Reported: DRESS 'Warm 62-86' beside TREND 'Cooler day, tomorrow 86'."""
    today = datetime.date(2026, 9, 20)
    hours = _hours([62, 65, 70, 75, 79, 82, 84, 85, 86, 85, 84, 82])
    days = [_day(today - datetime.timedelta(days=1), 89),   # Google's index 0
            _day(today, 86), _day(today + datetime.timedelta(days=1), 84),
            _day(today + datetime.timedelta(days=2), 83)]
    hist = {(today - datetime.timedelta(days=1)).isoformat(): {"hi_f": 89, "lo_f": 60}}

    cards = _cards(days, hours, today, hist)
    trend = next(c for c in cards if c["cat"] == "TREND")

    # 86 is TODAY's high; it must never be introduced as "tomorrow".
    assert "tomorrow 86" not in trend["detail"], trend
    assert trend["detail"] == "today 86° · 3° cooler than yesterday"
