"""Download, cache, and load Google weather icons from iconBaseUri."""
import os

import requests
from PIL import Image, ImageChops, ImageFilter

INK = (20, 22, 28)


def flatten_for_eink(img, size):
    """Make a transparent icon legible on white e-ink paper, as a size×size tile.

    Google's icons are drawn for dark UIs: cloud fills are white and vanish on
    paper. Rather than fill them (which turns clouds into solid blobs), trace
    the silhouette with a dark outline so shapes read as line-art while keeping
    saturated accents like the sun's yellow. The content is inset by 1px so the
    outline always stays inside the tile and never clips at the edge.
    """
    img = img.convert("RGBA")
    inner = img.resize((size - 2, size - 2), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(inner, (1, 1), inner)
    mask = canvas.split()[3].point(lambda v: 255 if v > 60 else 0)
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)
    outline = Image.new("RGBA", canvas.size, INK + (0,))
    outline.putalpha(ring)
    return Image.alpha_composite(outline, canvas)


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
        return flatten_for_eink(img, size)
    except (requests.RequestException, OSError):
        return blank
