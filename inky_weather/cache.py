"""Persist the last successful render so a failed fetch can re-show it (stale).

The Inky Impression is e-ink and holds its last image, but a failed hourly run
still needs the pixels to re-push with a staleness marker. Mirrors history.py:
atomic tmp + os.replace, best-effort, stored beside this package.
"""
import os

from PIL import Image

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "last_display.png")


def save_display(img, path=DEFAULT_PATH):
    """Persist the last-good RGB render (pre-quantization). Best-effort."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        img.save(tmp, "PNG")
        os.replace(tmp, path)
    except OSError:
        pass


def load_display(path=DEFAULT_PATH):
    """Return the cached image as an RGB PIL Image, or None if unavailable."""
    try:
        with Image.open(path) as im:
            return im.convert("RGB")
    except (OSError, ValueError):
        return None
