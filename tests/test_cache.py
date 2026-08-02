import os

from PIL import Image

from inky_weather import cache


def _img(color):
    return Image.new("RGB", (800, 480), color)


def test_save_then_load_roundtrips(tmp_path):
    path = os.path.join(tmp_path, "last.png")
    cache.save_display(_img((10, 20, 30)), path)
    loaded = cache.load_display(path)
    assert loaded is not None
    assert loaded.size == (800, 480)
    assert loaded.getpixel((0, 0)) == (10, 20, 30)


def test_load_missing_returns_none(tmp_path):
    assert cache.load_display(os.path.join(tmp_path, "nope.png")) is None


def test_load_unreadable_returns_none(tmp_path):
    path = os.path.join(tmp_path, "garbage.png")
    with open(path, "wb") as f:
        f.write(b"not a real png")
    assert cache.load_display(path) is None


def test_default_path_points_at_package():
    assert cache.DEFAULT_PATH.endswith(os.path.join("inky_weather", "last_display.png"))
