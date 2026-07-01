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
