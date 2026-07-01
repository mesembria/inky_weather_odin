import os
from unittest import mock

from PIL import Image

from inky_weather import icons


def test_cache_path_from_uri(tmp_path):
    p = icons.cache_path("https://maps.gstatic.com/weather/v1/partly_cloudy", str(tmp_path))
    assert p.endswith("partly_cloudy.png")
    assert str(tmp_path) in p


def test_get_icon_downloads_once_then_caches(tmp_path):
    uri = "https://maps.gstatic.com/weather/v1/clear"
    fake_png = _tiny_png_bytes()
    with mock.patch("inky_weather.icons.requests.get") as m:
        m.return_value.content = fake_png
        m.return_value.raise_for_status = lambda: None
        img1 = icons.get_icon(uri, size=40, cache_dir=str(tmp_path))
        img2 = icons.get_icon(uri, size=40, cache_dir=str(tmp_path))
    assert m.call_count == 1
    assert img1.size == (40, 40)
    assert img2.size == (40, 40)


def test_get_icon_missing_uri_returns_placeholder(tmp_path):
    img = icons.get_icon("", size=40, cache_dir=str(tmp_path))
    assert img.size == (40, 40)


def _tiny_png_bytes():
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()
