"""Persist Google daily highs/lows so the trend card can compare day-over-day.

The rest of the display trusts Google as the deterministic source (see
weather.recenter_bands, which re-anchors the mean-biased Open-Meteo ensemble onto
Google temps). Storing each day's Google high/low lets the trend card compare
Google-to-Google — bias-free and consistent with the numbers shown everywhere
else on screen — instead of against a different, warmer/cooler model.
"""
import datetime
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "daily_history.json")


def load_history(path=DEFAULT_PATH):
    """Return {iso_date: {"hi_f": int, "lo_f": int}}, or {} if unreadable."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and "hi_f" in v and "lo_f" in v}


def record_day(date, hi_f, lo_f, path=DEFAULT_PATH, keep=10):
    """Persist one day's Google high/low, pruning to the most recent `keep` days.

    Best-effort: swallows write errors so a storage problem never breaks the
    render. ISO date strings sort chronologically, so the oldest keys drop first.
    """
    hist = load_history(path)
    hist[date.isoformat()] = {"hi_f": hi_f, "lo_f": lo_f}
    for stale in sorted(hist)[:-keep]:
        del hist[stale]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(hist, f)
        os.replace(tmp, path)
    except OSError:
        pass


def trend_input(days, history, date):
    """Assemble the trend card's inputs from Google `days` + persisted `history`.

    `days` is the Google daily forecast (index 0 = today). Returns a dict
    {"today", "yesterday", "stretch_his"} or None when there is no forecast:
      - today:      {"hi_f","lo_f"} from the forecast (always present).
      - yesterday:  {"hi_f","lo_f"} recorded for date-1, or None (no history yet).
      - stretch_his: highs of the surrounding days (up to 3 persisted past days +
                     the next 3 forecast days), EXCLUDING today; used only for the
                     peak/dip upgrade.
    """
    if not days:
        return None
    today = {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]}
    yesterday = history.get((date - datetime.timedelta(days=1)).isoformat())
    past = []
    for back in (3, 2, 1):
        entry = history.get((date - datetime.timedelta(days=back)).isoformat())
        if entry:
            past.append(entry["hi_f"])
    forward = [d["hi_f"] for d in days[1:4]]
    return {"today": today, "yesterday": yesterday, "stretch_his": past + forward}
