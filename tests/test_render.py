from PIL import Image, ImageDraw
from inky_weather import render


def test_dimensions():
    assert render.WIDTH == 800
    assert render.HEIGHT == 480


def test_kind_color_known_kinds():
    for kind in ("dry", "rain", "storm", "snow", "mix"):
        c = render.kind_color(kind)
        assert isinstance(c, tuple) and len(c) == 3


def test_temp_color_hot_is_red_ish():
    r, g, b = render.temp_color(95)
    assert r > b


def test_load_font_returns_font():
    f = render.load_font(14)
    assert hasattr(f, "getbbox")


def test_draw_centered_text_runs():
    img = Image.new("RGB", (100, 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    render.draw_centered_text(d, "Hi", 50, 20, render.load_font(14), (0, 0, 0))
    assert img.tobytes() != Image.new("RGB", (100, 40), (255, 255, 255)).tobytes()


def test_layout_zones_sum_to_height():
    L = render.LAYOUT
    total = (L["header_h"] + L["temp_h"] + L["feels_h"]
             + L["precip_h"] + L["uv_h"] + L["hour_h"])
    assert total == render.HEIGHT


def test_layout_widths():
    L = render.LAYOUT
    assert L["hourly_w"] + L["daily_w"] == render.WIDTH


def _blank():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    return img, ImageDraw.Draw(img)


def test_draw_header_marks_top_band():
    img, d = _blank()
    render.draw_header(d, "Blacksburg, VA", "Tue Jun 30", "10:02 AM")
    assert any(img.getpixel((x, 10)) != render.PAPER for x in range(0, render.WIDTH, 20))


def _sample_hours():
    from inky_weather import weather
    import os, json
    fx = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")
    with open(os.path.join(fx, "hourly_response.json")) as f:
        return weather.parse_hourly(json.load(f), count=12)


def test_draw_hourly_panel_runs_and_marks():
    img, d = _blank()
    hours = _sample_hours()
    blank_icon = Image.new("RGBA", (34, 34), (0, 0, 0, 0))
    icons = [blank_icon] * len(hours)
    render.draw_hourly_panel(img, d, hours, icons)
    L = render.LAYOUT
    changed = sum(
        1 for x in range(0, L["hourly_w"], 5)
        for y in range(L["header_h"], render.HEIGHT, 5)
        if img.getpixel((x, y)) != render.PAPER
    )
    assert changed > 0


def _sample_days():
    from inky_weather import weather
    import os, json
    fx = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")
    with open(os.path.join(fx, "daily_response.json")) as f:
        return weather.parse_daily(json.load(f), count=10)


def test_draw_daily_row_runs():
    img, d = _blank()
    day = _sample_days()[0]
    blank_icon = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
    render.draw_daily_row(img, d, day, y=40, row_h=45, icon=blank_icon,
                          global_lo=10, global_hi=90)
    L = render.LAYOUT
    changed = any(
        img.getpixel((x, y)) != render.PAPER
        for x in range(L["hourly_w"] + 4, render.WIDTH, 5)
        for y in range(40, 85, 5)
    )
    assert changed


def test_render_display_returns_image():
    hours = _sample_hours()
    days = _sample_days()
    hour_icons = [Image.new("RGBA", (34, 34), (0, 0, 0, 0))] * len(hours)
    day_icons = [Image.new("RGBA", (26, 26), (0, 0, 0, 0))] * len(days)
    img = render.render_display(
        hours, days, hour_icons, day_icons,
        location_name="Blacksburg, VA", date_str="Tue Jun 30", updated_str="10:02 AM",
    )
    assert img.size == (render.WIDTH, render.HEIGHT)
    L = render.LAYOUT
    assert any(img.getpixel((L["hourly_w"] + 30, y)) != render.PAPER
               for y in range(render.HEIGHT))
