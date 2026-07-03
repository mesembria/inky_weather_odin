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
    render.draw_header(d, "Blacksburg, VA", "Tue Jun 30", "10:02 AM", ("HIGH", "green"))
    assert any(img.getpixel((x, 20)) != render.PAPER for x in range(0, render.WIDTH, 20))


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
    blank_icon = Image.new("RGBA", (render.ICON_SZ_DAY, render.ICON_SZ_DAY), (0, 0, 0, 0))
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
    day_icons = [Image.new("RGBA", (render.ICON_SZ_DAY, render.ICON_SZ_DAY), (0, 0, 0, 0))] * len(days)
    img = render.render_display(
        hours, days, hour_icons, day_icons,
        location_name="Blacksburg, VA", date_str="Tue Jun 30", updated_str="10:02 AM",
    )
    assert img.size == (render.WIDTH, render.HEIGHT)
    L = render.LAYOUT
    assert any(img.getpixel((L["hourly_w"] + 30, y)) != render.PAPER
               for y in range(render.HEIGHT))


def test_render_error_card_returns_image():
    img = render.render_error("No network: fetch failed")
    assert img.size == (render.WIDTH, render.HEIGHT)
    assert any(img.getpixel((x, render.HEIGHT // 2)) != render.PAPER
               for x in range(0, render.WIDTH, 10))


def test_draw_bolt_marks_pixels():
    img = Image.new("RGB", (30, 30), (255, 255, 255))
    d = ImageDraw.Draw(img)
    render.draw_bolt(d, 5, 5, 16, (230, 120, 0))
    assert img.tobytes() != Image.new("RGB", (30, 30), (255, 255, 255)).tobytes()


def test_display_font_loads_and_varies_weight():
    f = render.display_font(30, 600)
    assert hasattr(f, "getbbox")
    assert render.ACCENTS["red"] == render.RED


def test_draw_banner_marks_pixels():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
    d = ImageDraw.Draw(img)
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "63-81°", "accent": "orange"},
             {"cat": "STORMS", "verdict": "T-storms 2p", "detail": "65%", "accent": "red"}]
    render.draw_banner(d, cards)
    assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()


def test_draw_graph_runs_with_and_without_band():
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 20 * (i % 3), "precip_type": "RAIN", "thunder": 0, "uv": 3}
             for i in range(12)]
    bands = [(t - 3, t - 1, t + 1, t + 3) for t in (h["temp_f"] for h in hours)]
    for b in (bands, []):
        img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
        d = ImageDraw.Draw(img)
        render.draw_graph(img, d, hours, b, [None] * 12, 14, 160, render.WIDTH - 28, 300)
        assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()
