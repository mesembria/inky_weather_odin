"""Entry point: fetch forecasts, render the display, push to Inky (or PNG)."""
import argparse
import datetime
import os
import sys

from . import weather, icons, render, advice, history, cache, version

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ICON_CACHE = os.path.join(os.path.dirname(__file__), "assets", "icons")


def _load_config():
    try:
        from .config import config
        return config
    except ImportError:
        print("Missing inky_weather/config.py — copy config.example.py and fill it in.",
              file=sys.stderr)
        raise


def _safe(fn, default=None):
    """Run fn, returning default on any exception (graceful degradation)."""
    try:
        return fn()
    except Exception:
        return default


def _icons_for(items, size):
    return [icons.get_icon(item["icon_uri"], size, ICON_CACHE) for item in items]


def build_image(use_fixture, cfg):
    now = datetime.datetime.now()
    if use_fixture:
        hours, days = weather.load_from_fixtures(FIXTURE_DIR)
        fh = hours[0]["hour"]
        bands, gust = weather.load_ensemble_fixture(FIXTURE_DIR, fh)
        aqi = weather.load_airquality_fixture(FIXTURE_DIR, fh)
        dew = weather.load_dewpoint_fixture(FIXTURE_DIR, fh)
        sun = {"sunset": "8p", "sunrise": "6a"}
        # No persisted history offline. Provide a synthetic yesterday and a real
        # tomorrow (days[1]) so the preview renders a trend card either way — the
        # bundled fixture's high is already behind its window, so it renders the
        # forward "tomorrow vs today" pivot.
        trend = {"today": {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]},
                 "yesterday": {"hi_f": days[0]["hi_f"] + 6, "lo_f": days[0]["lo_f"] + 4},
                 "tomorrow": {"hi_f": days[1]["hi_f"], "lo_f": days[1]["lo_f"]},
                 "stretch_his": [d["hi_f"] for d in days[1:4]]}
    else:
        hours, days = weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])
        fh = hours[0]["hour"]
        bands_gust = _safe(lambda: weather.fetch_ensemble(cfg["lat"], cfg["long"], fh),
                           default=([], []))
        bands, gust = bands_gust
        aqi = _safe(lambda: weather.fetch_air_quality(cfg["lat"], cfg["long"], fh), default=[])
        sun = _safe(lambda: weather.fetch_sun(cfg["lat"], cfg["long"]), default={})
        dew = _safe(lambda: weather.fetch_dewpoint(cfg["lat"], cfg["long"], fh), default=[])
        # Trend compares Google-to-Google from persisted daily highs (the display's
        # trusted source), then records today's high for tomorrow's comparison.
        hist = _safe(history.load_history, default={})
        trend = history.trend_input(days, hist, now.date())
        _safe(lambda: history.record_day(now.date(), days[0]["hi_f"], days[0]["lo_f"]))

    # Anchor the ensemble spread on the trusted (Google) temps so the line always
    # sits inside its band (the two are different models — keep spread, drop bias).
    if bands:
        bands = weather.recenter_bands(bands, [h["temp_f"] for h in hours])
    # Attach dew point so the advice layer can judge mugginess from humidity.
    for i, h in enumerate(hours):
        if i < len(dew) and dew[i] is not None:
            h["dew_f"] = dew[i]

    hour_icons = _icons_for(hours, render.ICON_SZ_HOUR)
    cards = advice.build_cards(hours, bands, gust, aqi, sun, now.date(), days=days, trend=trend)
    badge = advice.confidence(bands)
    return render.render_display(
        hours, bands, hour_icons, cards, badge,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M%p").lower().lstrip("0"),
        version=version.get_version(),
    )


def push_to_display(img):
    """Send an image to the Inky Impression. Imported lazily (Pi-only dep)."""
    from inky.auto import auto
    display = auto()
    display.set_image(img.convert("RGB"))
    display.show()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inky weather display")
    parser.add_argument("--fixture", action="store_true",
                        help="Use bundled fixtures instead of the live API")
    parser.add_argument("--out", metavar="PATH",
                        help="Write PNG to PATH instead of the display")
    args = parser.parse_args(argv)

    use_fixture = args.fixture
    try:
        if use_fixture:
            cfg = {"location_name": "Blacksburg, VA"}
        else:
            cfg = _load_config()
        img = build_image(use_fixture, cfg)
        if not use_fixture:
            cache.save_display(img)          # best-effort; keep last-good on disk
    except Exception as exc:  # keep last-good forecast up rather than a blank error
        cached = None if use_fixture else cache.load_display()
        if cached is not None:
            img = render.stamp_stale(cached)
        else:
            img = render.render_error(str(exc)[:80])

    if args.out:
        img.save(args.out)
        print("Wrote", args.out)
    else:
        push_to_display(img)


if __name__ == "__main__":
    main()
