"""Entry point: fetch forecasts, render the display, push to Inky (or PNG)."""
import argparse
import datetime
import os
import sys

from . import weather, icons, render, advice

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
    if use_fixture:
        hours, _days = weather.load_from_fixtures(FIXTURE_DIR)
        bands, gust = weather.load_ensemble_fixture(FIXTURE_DIR, hours[0]["hour"])
        aqi = weather.load_airquality_fixture(FIXTURE_DIR, hours[0]["hour"])
        sun = {"sunset": "8p", "sunrise": "6a"}
    else:
        hours, _days = weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])
        fh = hours[0]["hour"]
        bands_gust = _safe(lambda: weather.fetch_ensemble(cfg["lat"], cfg["long"], fh),
                           default=([], []))
        bands, gust = bands_gust
        aqi = _safe(lambda: weather.fetch_air_quality(cfg["lat"], cfg["long"], fh), default=[])
        sun = _safe(lambda: weather.fetch_sun(cfg["lat"], cfg["long"]), default={})

    hour_icons = _icons_for(hours, render.ICON_SZ_HOUR)
    now = datetime.datetime.now()
    cards = advice.build_cards(hours, bands, gust, aqi, sun, now.date())
    badge = advice.confidence(bands)
    return render.render_display(
        hours, bands, hour_icons, cards, badge,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M%p").lower().lstrip("0"),
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

    try:
        if args.fixture:
            cfg = {"location_name": "Blacksburg, VA"}
        else:
            cfg = _load_config()
        img = build_image(args.fixture, cfg)
    except Exception as exc:  # render an error card rather than crash silently
        img = render.render_error(str(exc)[:80])

    if args.out:
        img.save(args.out)
        print("Wrote", args.out)
    else:
        push_to_display(img)


if __name__ == "__main__":
    main()
