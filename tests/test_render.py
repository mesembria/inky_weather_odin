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
