import datetime
from inky_weather import advice


def _hours(temps, feels=None, day=True, pop=0, ptype="RAIN", thunder=0, uv=3):
    feels = feels or temps
    out = []
    for i, (t, f) in enumerate(zip(temps, feels)):
        h = (9 + i) % 24
        out.append({"hour": h, "ampm_label": "{}{}".format(h % 12 or 12,
                    "a" if h < 12 else "p"), "is_daytime": day, "condition": "CLEAR",
                    "icon_uri": "", "temp_f": t, "feels_f": f, "pop": pop,
                    "precip_type": ptype, "thunder": thunder, "uv": uv})
    return out


def test_temp_card_cold_band_fills_30s_40s():
    c = advice.temp_card(_hours([40, 42, 44, 45, 44, 42, 40, 38, 37, 36, 35, 34]))
    assert c["verdict"] == "Cold"
    assert c["cat"] == "DRESS"


def test_temp_card_warm_muggy():
    c = advice.temp_card(_hours([80, 82, 83, 84, 83, 82, 81, 80, 79, 78, 77, 76],
                                feels=[86, 88, 89, 90, 89, 88, 87, 86, 85, 84, 83, 82]))
    assert c["verdict"] == "Warm & muggy"


def test_moon_full_is_high():
    # 2026-07-28 is ~full
    assert advice.moon_illumination(datetime.date(2026, 7, 28)) > 0.9


def test_confidence_tight_band_is_high():
    bands = [(70, 71, 73, 74)] * 12
    label, accent = advice.confidence(bands)
    assert label == "HIGH CONFIDENCE" and accent == "green"


def test_daytime_storm_scores_high():
    hrs = _hours([78]*12, thunder=65, pop=90)
    cards = dict((s, c["verdict"]) for s, c in advice._situational(hrs, 5, 20))
    assert any(v.startswith("T-storms") for v in cards.values())


def test_overnight_storm_uses_windows_shut():
    hrs = _hours([64]*12, day=False, thunder=40, pop=80)
    cards = [c for _, c in advice._situational(hrs, 5, 20) if c["cat"] == "OVERNIGHT"]
    assert cards and cards[0]["verdict"] == "Storms overnight"


def test_rain_card_is_daytime_timing():
    hrs = _hours([60]*12, pop=70)
    rain = [c for _, c in advice._situational(hrs, 5, 20) if c["cat"] == "OUTDOORS"]
    assert rain and rain[0]["verdict"].startswith("Rain ")
