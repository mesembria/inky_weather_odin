import datetime
from inky_weather import advice


def _hours(temps, feels=None, day=True, pop=0, ptype="RAIN", thunder=0, uv=3, dew=None):
    feels = feels or temps
    out = []
    for i, (t, f) in enumerate(zip(temps, feels)):
        h = (9 + i) % 24
        hr = {"hour": h, "ampm_label": "{}{}".format(h % 12 or 12,
              "a" if h < 12 else "p"), "is_daytime": day, "condition": "CLEAR",
              "icon_uri": "", "temp_f": t, "feels_f": f, "pop": pop,
              "precip_type": ptype, "thunder": thunder, "uv": uv}
        if dew is not None:
            hr["dew_f"] = dew
        out.append(hr)
    return out


def test_temp_card_cold_band_fills_30s_40s():
    c = advice.temp_card(_hours([40, 42, 44, 45, 44, 42, 40, 38, 37, 36, 35, 34]))
    assert c["verdict"] == "Cold"
    assert c["cat"] == "DRESS"


def test_temp_card_warm_muggy_from_dewpoint():
    # warm day with a high daytime dew point -> muggy
    c = advice.temp_card(_hours([80, 82, 83, 84, 83, 82, 81, 80, 79, 78, 77, 76], dew=66))
    assert c["verdict"] == "Warm & muggy"


def test_temp_card_warm_dry_not_muggy():
    # a dry-CO-style warm day: high feels-like but LOW dew point -> not muggy
    c = advice.temp_card(_hours([80, 82, 83, 84, 83, 82, 81, 80, 79, 78, 77, 76],
                                feels=[86, 88, 89, 90, 89, 88, 87, 86, 85, 84, 83, 82], dew=48))
    assert c["verdict"] == "Warm"


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


def test_build_cards_calm_day_fills_info_tier():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"}, datetime.date(2026, 7, 15))
    assert cards[0]["cat"] == "DRESS"
    cats = [c["cat"] for c in cards]
    assert "DAYLIGHT" in cats or "OUTDOORS" in cats   # info tier filled a slot


def test_build_cards_full_moon_night():
    hrs = _hours([60, 58, 56, 55, 54, 53, 52, 52, 53, 54, 55, 56], day=False)
    cards = advice.build_cards(hrs, [], [], [], {}, datetime.date(2026, 7, 28))
    assert any(c["cat"] == "MOON" for c in cards)


def test_build_cards_hazards_beat_info_tier():
    hrs = _hours([78]*12, thunder=65, pop=90)
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"}, datetime.date(2026, 7, 15))
    assert cards[0]["cat"] == "DRESS"
    assert any(c["cat"] == "STORMS" for c in cards)
    assert not any(c["cat"] in ("MOON", "DAYLIGHT") for c in cards)  # crowded out


def _t(hi, lo=None):
    return {"hi_f": hi, "lo_f": lo if lo is not None else hi - 20}


def _days(highs, names=None):
    names = names or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [{"hi_f": h, "name": n} for h, n in zip(highs, names)]


def _trend(today, yesterday, stretch_his):
    return {"today": today, "yesterday": yesterday, "stretch_his": stretch_his}


def test_build_cards_includes_trend():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15),
                               trend=_trend(_t(78, 58), _t(85, 63), []))
    assert any(c["cat"] == "TREND" and c["verdict"] == "Cooler day" for c in cards)


def test_build_cards_hazard_can_bump_trend():
    # multiple hazards (storm + gusty wind) fill both non-DRESS slots ahead of TREND
    hrs = _hours([78] * 12, thunder=65, pop=90)   # STORMS=90, OUTDOORS(rain)=72
    cards = advice.build_cards(hrs, [], [40] * 12, [], {}, datetime.date(2026, 7, 15),
                               trend=_trend(_t(78, 58), _t(85, 63), []))
    assert any(c["cat"] == "STORMS" for c in cards)
    assert not any(c["cat"] == "TREND" for c in cards)


def test_build_cards_trend_absent_without_data():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15), trend=None)
    assert not any(c["cat"] == "TREND" for c in cards)


def test_build_cards_includes_outlook():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {}, datetime.date(2026, 7, 15),
                               days=_days([70, 74, 78, 82]))
    assert any(c["cat"] == "OUTLOOK" for c in cards)


def test_trend_card_cooler_day():
    s, c = advice._trend_card(_t(78, 58), _t(85, 65), [])
    assert s == advice.TREND_SCORE and c["cat"] == "TREND"
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"
    assert c["detail"] == "today 78° · 7° cooler than yesterday"


def test_trend_card_drops_low_delta():
    # the low-delta append is gone; only the high framing remains
    s, c = advice._trend_card(_t(78, 58), _t(85, 63), [])
    assert c["detail"] == "today 78° · 7° cooler than yesterday"
    assert "low" not in c["detail"]


def test_trend_card_steady_when_flat():
    s, c = advice._trend_card(_t(80), _t(80), [])
    assert c["verdict"] == "Steady" and c["accent"] == "gray"
    assert c["detail"] == "today 80° · same as yesterday"


def test_trend_card_much_warmer():
    s, c = advice._trend_card(_t(76, 56), _t(64, 44), [])
    assert c["verdict"] == "Much warmer" and c["accent"] == "orange"
    assert c["detail"] == "today 76° · 12° warmer than yesterday"


def test_trend_card_coolest_stretch_upgrade():
    # today strictly the lowest high of the surrounding stretch, by >= 3
    s, c = advice._trend_card(_t(70), _t(72), [84, 85, 86, 80])
    assert c["verdict"] == "Coolest stretch" and c["accent"] == "blue"
    assert c["detail"] == "today 70° · coolest day this week"


def test_trend_card_warmest_stretch_upgrade():
    s, c = advice._trend_card(_t(90), _t(80), [76, 73, 71, 80])
    assert c["verdict"] == "Warmest stretch" and c["accent"] == "orange"
    assert c["detail"] == "today 90° · warmest day this week"


def test_trend_card_upgrade_without_yesterday():
    # a peak/dip can show even before a "yesterday" high has been recorded
    s, c = advice._trend_card(_t(70), None, [84, 85, 86, 80])
    assert c["verdict"] == "Coolest stretch"


def test_trend_card_none_without_today():
    assert advice._trend_card(None, _t(80), [84, 85, 86, 80]) is None


def test_trend_card_none_first_run_no_yesterday():
    # no yesterday yet and not a stretch extreme (too few surrounding days) -> no card
    assert advice._trend_card(_t(80), None, [79, 81, 82]) is None


def test_trend_card_short_stretch_skips_upgrade():
    # only 3 surrounding days (pure forecast, no history): even though today (70)
    # sits well below them, no peak/dip framing fires — falls back to day-over-day
    s, c = advice._trend_card(_t(70), _t(76), [84, 85, 86])
    assert c["verdict"] == "Cooler day"


def test_trend_card_dhi_minus3_is_cooler_day():
    s, c = advice._trend_card(_t(77), _t(80), [])
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"


def test_trend_card_dhi_plus3_is_warmer_day():
    s, c = advice._trend_card(_t(80), _t(77), [])
    assert c["verdict"] == "Warmer day" and c["accent"] == "orange"


def test_trend_card_forward_tomorrow_warmer():
    s, c = advice._trend_card(_t(70), _t(72), [], tomorrow=_t(75), forward=True)
    assert c["verdict"] == "Warmer day" and c["accent"] == "orange"
    assert c["detail"] == "tomorrow 75° · 5° warmer than today"


def test_trend_card_forward_tomorrow_cooler():
    s, c = advice._trend_card(_t(80), _t(78), [], tomorrow=_t(74), forward=True)
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"
    assert c["detail"] == "tomorrow 74° · 6° cooler than today"


def test_trend_card_forward_steady():
    s, c = advice._trend_card(_t(80), _t(70), [], tomorrow=_t(80), forward=True)
    assert c["verdict"] == "Steady"
    assert c["detail"] == "tomorrow 80° · same as today"


def test_trend_card_forward_none_without_tomorrow():
    assert advice._trend_card(_t(80), _t(70), [], tomorrow=None, forward=True) is None


def test_trend_card_dhi_minus10_is_much_cooler():
    s, c = advice._trend_card(_t(75), _t(85), [])
    assert c["verdict"] == "Much cooler" and c["accent"] == "blue"


def test_trend_card_dhi_plus10_is_much_warmer():
    s, c = advice._trend_card(_t(85), _t(75), [])
    assert c["verdict"] == "Much warmer" and c["accent"] == "orange"


def test_outlook_warming_trend():
    s, c = advice._outlook_card(_days([70, 74, 78, 82]))
    assert s == advice.OUTLOOK_SCORE and c["cat"] == "OUTLOOK"
    assert c["verdict"] == "Warming trend" and c["accent"] == "orange"
    assert c["detail"] == "→ 82° by Thu"


def test_outlook_cooling_trend():
    s, c = advice._outlook_card(_days([82, 78, 74, 70]))
    assert c["verdict"] == "Cooling trend" and c["accent"] == "blue"
    assert c["detail"] == "→ 70° by Thu"


def test_outlook_none_when_change_below_threshold():
    assert advice._outlook_card(_days([70, 72, 71, 74])) is None   # net +4 < 8


def test_outlook_none_when_reversal_dominates():
    # net +8 but a -6 reversal in the middle: not a consistent direction
    assert advice._outlook_card(_days([70, 84, 78, 78])) is None


def test_outlook_none_without_enough_days():
    assert advice._outlook_card(_days([70, 74, 80])) is None


def test_outlook_net_8_exactly_fires_warming_trend():
    s, c = advice._outlook_card(_days([70, 72, 74, 78]))
    assert c["verdict"] == "Warming trend"
