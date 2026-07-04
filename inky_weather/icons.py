"""Download, cache, and load Google weather icons from iconBaseUri."""
import os

import requests
from PIL import Image, ImageChops, ImageFilter

INK = (20, 22, 28)


def flatten_for_eink(img):
    """Make a transparent icon legible on white e-ink paper.

    Google's icons are drawn for dark UIs: cloud fills are white and vanish on
    paper. Recolor near-white / near-neutral opaque pixels to ink (keeping
    saturated accents like the sun's yellow), then trace the silhouette with a
    1px ink outline so even light shapes have a defined edge.
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            sat = max(r, g, b) - min(r, g, b)
            if sat < 45 and max(r, g, b) > 150:      # white/light-neutral fill
                px[x, y] = (INK[0], INK[1], INK[2], a)
    mask = img.split()[3].point(lambda v: 255 if v > 60 else 0)
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)
    outline = Image.new("RGBA", img.size, INK + (0,))
    outline.putalpha(ring)
    return Image.alpha_composite(outline, img)


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
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return flatten_for_eink(img)
    except (requests.RequestException, OSError):
        return blank
