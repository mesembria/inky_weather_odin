"""Pure advice logic: turn parsed forecast numbers into <=3 ranked cards.

A card is a dict {"cat", "verdict", "detail", "accent"} where accent is one of
"red"|"orange"|"blue"|"green"|"purple"|"ink"|"gray" (render maps names to RGB).
"""
import datetime
import math

ICE_TYPES = ("ICE", "SLEET", "FREEZING_RAIN")
MUGGY_DEWPOINT_F = 60   # daytime dew point at/above this reads as "muggy"


def _card(cat, verdict, detail, accent):
    return {"cat": cat, "verdict": verdict, "detail": detail, "accent": accent}


def moon_illumination(date):
    """Illuminated fraction of the moon (0=new, 1=full) for a date."""
    ref = datetime.date(2000, 1, 6)          # a known new moon
    days = (date - ref).days + 0.5
    phase = (days % 29.53058867) / 29.53058867
    return (1 - math.cos(2 * math.pi * phase)) / 2


def confidence(bands):
    """(label, accent) from the mean p10-p90 width of the ensemble band."""
    if not bands:
        return ("NO ENSEMBLE", "gray")
    avg = sum(p90 - p10 for p10, _, _, p90 in bands) / len(bands)
    if avg < 6:
        return ("HIGH CONFIDENCE", "green")
    if avg < 10:
        return ("MIXED CONFIDENCE", "orange")
    return ("LOW AGREEMENT", "red")


def temp_card(hours):
    """Slot-1 'what to wear' card: a plain state line keyed on the day's high."""
    T = [h["temp_f"] for h in hours]
    hi, lo = max(T), min(T)
    uvmax = max(h["uv"] for h in hours)
    # "muggy" is a humidity call, so key it on daytime dew point (≥ 60°F feels
    # sticky) — not feels-like vs temp, which mislabels dry days as muggy.
    day_dp = [h["dew_f"] for h in hours if h.get("is_daytime") and h.get("dew_f") is not None]
    muggy = bool(day_dp) and max(day_dp) >= MUGGY_DEWPOINT_F
    wet = any(h["pop"] >= 50 for h in hours)
    frost = " · frost AM" if lo <= 32 else ""
    if hi >= 100:
        return _card("DRESS", "Dangerous heat", "{}-{}° · hydrate, shade".format(lo, hi), "red")
    if hi >= 90:
        return _card("DRESS", "Hot", "{}-{}° · UV {}, shade".format(lo, hi, uvmax), "red")
    if hi >= 80:
        return _card("DRESS", "Warm & muggy" if muggy else "Warm",
                     "{}-{}° · {}".format(lo, hi, "humid" if muggy else "pleasant"), "orange")
    if hi >= 62:
        return _card("DRESS", "Mild", "{}-{}° · easy layers".format(lo, hi), "green")
    if hi >= 48:
        return _card("DRESS", "Cool & damp" if wet else "Cool",
                     "{}-{}° · layers".format(lo, hi), "blue")
    if hi >= 33:
        return _card("DRESS", "Cold", "{}-{}° · coat{}".format(lo, hi, frost), "blue")
    return _card("DRESS", "Frigid", "{}-{}° · bundle up".format(lo, hi), "blue")


def _w0(hs):
    return hs[0]["ampm_label"].lower()


def _w1(hs):
    return hs[-1]["ampm_label"].lower()


# tie-break precedence for equal scores: lower index = wins
_PRECEDENCE = ["ICE", "SNOW", "STORMS", "SMOKE", "WIND", "OUTDOORS", "SUN",
               "TREND", "OVERNIGHT", "SPREAD", "MOON", "DAYLIGHT"]


def _tiebreak_key(scored):
    score, card = scored
    try:
        rank = _PRECEDENCE.index(card["cat"])
    except ValueError:
        rank = len(_PRECEDENCE)
    return (-score, rank)


def _band_width(bands):
    return max((p90 - p10 for p10, _, _, p90 in bands), default=0)


def _situational(hours, gust, aqi):
    """Daytime-framed hazard cards + one OVERNIGHT roll-up. Returns [(score, card)]."""
    C = []
    day_h = [h for h in hours if h["is_daytime"]]
    night_h = [h for h in hours if not h["is_daytime"]]
    ice_day = [h for h in day_h if h["precip_type"] in ICE_TYPES and h["pop"] >= 30]
    snow_day = [h for h in day_h if h["precip_type"] == "SNOW" and h["pop"] >= 30]
    wet_day = [h for h in day_h if h["pop"] >= 50
               and h["precip_type"] not in ICE_TYPES + ("SNOW",)]
    uvmax = max((h["uv"] for h in day_h), default=0)
    dstorm = max(day_h, key=lambda h: h["thunder"]) if day_h else None
    dthun = dstorm["thunder"] if dstorm else 0

    if ice_day:
        C.append((97, _card("ICE", "Ice {}-{}".format(_w0(ice_day), _w1(ice_day)),
                            "Icy roads · avoid driving", "purple")))
    if snow_day:
        C.append((95, _card("SNOW", "Snow {}".format("all day" if len(snow_day) >= 8 else _w0(snow_day)),
                            "{}\" likely · roads slick".format(6 if len(snow_day) >= 8 else 3), "purple")))
    if dthun >= 45:
        C.append((90, _card("STORMS", "T-storms {}".format(dstorm["ampm_label"].lower()),
                            "{}% · brief, heavy".format(dthun), "red")))
    elif dthun >= 25:
        C.append((68, _card("STORMS", "Stray storm {}".format(dstorm["ampm_label"].lower()),
                            "{}% · mainly dry".format(dthun), "orange")))
    if aqi >= 150:
        C.append((88, _card("SMOKE", "Unhealthy air", "AQI {} · stay indoors".format(aqi), "purple")))
    elif aqi >= 100:
        C.append((64, _card("SMOKE", "Hazy air", "AQI {} · limit exertion".format(aqi), "orange")))
    if gust >= 35:
        C.append((80, _card("WIND", "Gusty", "Gusts {} mph · secure loose items".format(gust), "orange")))
    elif gust >= 25:
        C.append((56, _card("WIND", "Breezy", "Gusts {} mph".format(gust), "blue")))
    if wet_day:
        C.append((72, _card("OUTDOORS", "Rain {}-{}".format(_w0(wet_day), _w1(wet_day)),
                            "{}% · umbrella".format(max(h["pop"] for h in wet_day)), "blue")))
    if day_h and uvmax >= 9:
        C.append((60, _card("SUN", "Extreme UV", "Index {} · cover up".format(uvmax), "red")))
    elif day_h and uvmax >= 6:
        C.append((44, _card("SUN", "Strong UV", "Index {} midday · hat+SPF".format(uvmax), "orange")))

    T = [h["temp_f"] for h in hours]
    half = T[len(T) // 2:]
    base = len(T) // 2
    lo_late, hi_late = min(half), max(half)
    cool_sw, warm_sw = T[0] - lo_late, hi_late - T[0]
    if warm_sw >= 18 and warm_sw >= cool_sw:
        j = base + half.index(hi_late)
        C.append((58, _card("TREND", "Warming up",
                            "{}°→{}° by {}".format(T[0], hi_late, hours[j]["ampm_label"].lower()), "orange")))
    elif cool_sw >= 18:
        j = base + half.index(lo_late)
        C.append((58, _card("TREND", "Cooling off",
                            "{}°→{}° by {}".format(T[0], lo_late, hours[j]["ampm_label"].lower()), "blue")))

    if night_h:
        nlo = min(h["temp_f"] for h in night_h)
        nstorm = max(h["thunder"] for h in night_h)
        nwet = any(h["pop"] >= 50 and h["precip_type"] not in ICE_TYPES + ("SNOW",) for h in night_h)
        nsnow = any(h["precip_type"] == "SNOW" and h["pop"] >= 30 for h in night_h)
        nice = any(h["precip_type"] in ICE_TYPES and h["pop"] >= 30 for h in night_h)
        if nice and not ice_day:
            card, sc = _card("OVERNIGHT", "Ice overnight", "Low {}° · icy roads AM".format(nlo), "purple"), 88
        elif nstorm >= 30 and dthun < 25:
            card, sc = _card("OVERNIGHT", "Storms overnight", "Low {}° · windows shut".format(nlo), "red"), 85
        elif nsnow and not snow_day:
            card, sc = _card("OVERNIGHT", "Snow overnight", "Low {}° · roads slick AM".format(nlo), "purple"), 82
        elif nwet and not wet_day:
            card, sc = _card("OVERNIGHT", "Rain overnight", "Low {}° · windows shut".format(nlo), "blue"), 60
        elif nlo <= 45:
            card, sc = _card("OVERNIGHT", "Cold night", "Low {}° · heat on".format(nlo), "blue"), 55
        elif nlo >= 70:
            card, sc = _card("OVERNIGHT", "Warm night", "Low {}° · stuffy, fan on".format(nlo), "orange"), 50
        elif nlo <= 68:
            card, sc = _card("OVERNIGHT", "Windows open", "Low {}° · comfortable".format(nlo), "green"), 50
        else:
            card, sc = _card("OVERNIGHT", "Mild night", "Low {}°".format(nlo), "green"), 50
        C.append((sc, card))
    return C


def _info_tier(hours, bands, sun, date, has_hazard):
    C = []
    day_h = [h for h in hours if h["is_daytime"]]
    night_h = [h for h in hours if not h["is_daytime"]]
    daymost = len(day_h) >= len(night_h)
    # SWING
    if bands:
        widths = [(p90 - p10, i) for i, (p10, _, _, p90) in enumerate(bands)]
        wmax, wi = max(widths)
        if wmax >= 15:
            p10, _, _, p90 = bands[wi]
            C.append((40, _card("SPREAD", "Could be {}-{}°".format(int(p10), int(p90)),
                                "models split by {}".format(hours[wi]["ampm_label"].lower()), "purple")))
    # MOON
    if night_h:
        il = moon_illumination(date)
        if il >= 0.90:
            C.append((36, _card("MOON", "Full moon" if il >= 0.985 else "Nearly full moon",
                                "{}% lit · bright night".format(int(round(il * 100))), "orange")))
    # calm nudge
    if not has_hazard:
        C.append((34, _card("OUTDOORS", "Get outside", "Clear & calm ahead", "green") if daymost
                  else _card("OVERNIGHT", "Quiet night", "Clear & calm", "green")))
    # DAYLIGHT
    if daymost and sun.get("sunset"):
        C.append((32, _card("DAYLIGHT", "Sunset {}".format(sun["sunset"]), "plan outdoor time", "orange")))
    elif not daymost and sun.get("sunrise"):
        C.append((32, _card("DAYLIGHT", "Sunrise {}".format(sun["sunrise"]), "first light", "orange")))
    return C


def build_cards(hours, bands, gust, aqi, sun, date):
    sun = sun or {}
    gmax = max(gust) if gust else 0
    amax = max(aqi) if aqi else 0
    cards = [temp_card(hours)]
    scored = _situational(hours, gmax, amax)
    has_hazard = any(s >= 50 for s, _ in scored)
    scored += _info_tier(hours, bands, sun, date, has_hazard)
    scored.sort(key=_tiebreak_key)
    cards += [c for _, c in scored[:2]]
    return cards
