"""Entry point: fetch forecasts, render the display, push to Inky (or PNG)."""
import argparse
import datetime
import os
import sys

from . import weather, icons, render

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


def _gather(use_fixture, cfg):
    if use_fixture:
        return weather.load_from_fixtures(FIXTURE_DIR)
    return weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])


def _icons_for(items, size):
    return [icons.get_icon(item["icon_uri"], size, ICON_CACHE) for item in items]


def build_image(use_fixture, cfg):
    hours, days = _gather(use_fixture, cfg)
    hour_icons = _icons_for(hours, render.ICON_SZ_HOUR)
    day_icons = _icons_for(days, render.ICON_SZ_DAY)
    now = datetime.datetime.now()
    return render.render_display(
        hours, days, hour_icons, day_icons,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M %p"),
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
