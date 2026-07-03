"""Pure advice logic: turn parsed forecast numbers into <=3 ranked cards.

A card is a dict {"cat", "verdict", "detail", "accent"} where accent is one of
"red"|"orange"|"blue"|"green"|"purple"|"ink" (render maps names to RGB).
"""
import datetime
import math

ICE_TYPES = ("ICE", "SLEET", "FREEZING_RAIN")


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
    FL = [h["feels_f"] for h in hours]
    hi, lo = max(T), min(T)
    uvmax = max(h["uv"] for h in hours)
    muggy = any(f > t + 2 for f, t in zip(FL, T))
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
