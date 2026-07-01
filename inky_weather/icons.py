"""Download, cache, and load Google weather icons from iconBaseUri."""
import os

import requests
from PIL import Image


def cache_path(icon_uri, cache_dir):
    """Local cache filename for an icon URI (last path segment + .png)."""
    name = icon_uri.rstrip("/").rsplit("/", 1)[-1] or "unknown"
    return os.path.join(cache_dir, name + ".png")


def _download(icon_uri, dest):
    resp = requests.get(icon_uri + ".png", timeout=20)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def get_icon(icon_uri, size, cache_dir):
    """Return an RGBA PIL image for the given icon URI, resized to size x size.

    Downloads and caches on first use. Returns a blank transparent image if the
    URI is empty or the download/open fails (so rendering never crashes).
    """
    os.makedirs(cache_dir, exist_ok=True)
    blank = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if not icon_uri:
        return blank
    path = cache_path(icon_uri, cache_dir)
    try:
        if not os.path.exists(path):
            _download(icon_uri, path)
        img = Image.open(path).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)
    except (requests.RequestException, OSError):
        return blank
