"""Pillow rendering for the Inky Impression weather display."""
import os
from PIL import Image, ImageDraw, ImageFont
from . import weather

WIDTH = 800
HEIGHT = 480

# Palette-friendly RGB colors (quantized to the panel by the inky library).
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
PAPER = (255, 255, 255)      # background
RED = (200, 30, 30)
BLUE = (30, 70, 200)
GREEN = (30, 140, 60)
YELLOW = (230, 190, 0)
ORANGE = (230, 120, 0)

# Semantic mapping. Storm defaults to RED so it reads on 6-color panels.
COLOR_RAIN = BLUE
COLOR_STORM = RED
COLOR_SNOW = GREEN          # distinct from rain on a limited palette
COLOR_MIX = GREEN
COLOR_DRY = (210, 210, 210)

ICON_SZ_HOUR = 28

# --- new redesign palette + font (additive) ---
INK = (20, 22, 28)
PURPLE = (150, 40, 140)
GRAY = (120, 122, 130)
FAINT = (225, 226, 230)

ACCENTS = {"red": RED, "orange": ORANGE, "blue": BLUE, "green": GREEN,
           "purple": PURPLE, "ink": INK, "gray": GRAY}

_BADGE_GLYPH = {"HIGH CONFIDENCE": "◆", "MIXED CONFIDENCE": "◈", "LOW AGREEMENT": "◇"}

_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Oswald.ttf")


def display_font(size, weight=600):
    """Bundled Oswald at the given size and weight (300 or 600)."""
    f = ImageFont.truetype(_FONT_PATH, int(size))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def temp_color(temp_f):
    if temp_f >= 80:
        return RED
    if temp_f >= 72:
        return ORANGE
    if temp_f >= 55:
        return INK
    return BLUE


# Layout constants for banner cards
BANNER_Y = 50
BANNER_H = 104
HEADER_RULE_Y = 40


def _ctext(d, t, cx, cy, font, fill, anchor="mm"):
    """Draw text with anchor point."""
    d.text((cx, cy), t, font=font, fill=fill, anchor=anchor)


# Graph layout constants for ensemble display
GRAPH_Y = BANNER_Y + BANNER_H + 2
GRAPH_H = HEIGHT - GRAPH_Y - 8
BAND_OUT = (213, 220, 240)
BAND_IN = (178, 190, 224)

_KIND_BAR = {"storm": RED, "snow": PURPLE, "mix": PURPLE, "rain": BLUE, "dry": BLUE}


def draw_header(draw, location, date_str, updated_str, badge):
    """Draw the header band with location, date, confidence badge, and updated time."""
    _ctext(draw, (location or "").upper(), 20, 20, display_font(26, 600), INK, anchor="lm")
    w = draw.textlength((location or "").upper(), font=display_font(26, 600))
    _ctext(draw, date_str, 28 + w, 22, display_font(15, 600), INK, anchor="lm")
    if badge:
        label, accent = badge
        glyph = _BADGE_GLYPH.get(label, "◇")
        _ctext(draw, glyph + " " + label, WIDTH - 20, 15, display_font(12, 600),
               ACCENTS.get(accent, INK), anchor="rm")
    _ctext(draw, updated_str + " · NEXT 12H", WIDTH - 20, 30, display_font(12, 600), INK, anchor="rm")
    draw.line([20, HEADER_RULE_Y, WIDTH - 20, HEADER_RULE_Y], fill=INK, width=2)


def _draw_card(draw, x, y, w, h, card):
    """Draw a single card with category, verdict, and detail."""
    accent = ACCENTS.get(card["accent"], INK)
    _ctext(draw, card["cat"], x + 14, y + 15, display_font(13, 600), accent, anchor="lm")
    vf = display_font(30 if len(card["verdict"]) <= 15 else 26, 600)
    _ctext(draw, card["verdict"], x + 14, y + 45, vf, INK, anchor="lm")
    _ctext(draw, card["detail"], x + 14, y + h - 13, display_font(14, 600), INK, anchor="lm")


def draw_banner(draw, cards):
    """Draw 2-3 cards across the banner."""
    cw = (WIDTH - 40) / 3
    for i, card in enumerate(cards):
        x = 20 + i * cw
        _draw_card(draw, x, BANNER_Y, cw, BANNER_H, card)
        if i > 0:
            draw.line([x, BANNER_Y + 8, x, BANNER_Y + BANNER_H - 8], fill=INK, width=1)
    draw.line([20, BANNER_Y + BANNER_H, WIDTH - 20, BANNER_Y + BANNER_H], fill=INK, width=1)


def draw_graph(img, draw, hours, bands, icons, gx, gy, gw, gh):
    n = len(hours)
    temps = [h["temp_f"] for h in hours]
    has_band = len(bands) == n and n > 0
    lows = [b[0] for b in bands] if has_band else temps
    highs = [b[3] for b in bands] if has_band else temps
    mn, mx = min(lows), max(highs)
    rng = (mx - mn) or 1
    bandh = 82
    axis_y = gy + gh - 16
    top = gy + 40
    plot_h = (axis_y - bandh) - top
    pad_top = 24        # headroom so the highest point's label clears the icon row
    lx = gx + 30
    xs = [lx + (gw - 32) * (i + 0.5) / n for i in range(n)]

    def Y(t):
        return (top + pad_top) + (plot_h - pad_top) * (1 - (t - mn) / rng)

    # temp gridlines + labels
    lo10 = int((mn // 10) * 10)
    hi10 = int((mx // 10 + 1) * 10)
    step = 10 if (hi10 - lo10) >= 20 else 5
    for g in range(lo10, hi10 + 1, step):
        if g < mn - 2 or g > mx + 2:
            continue
        gyv = Y(g)
        draw.line([lx, gyv, gx + gw, gyv], fill=(230, 231, 236), width=1)
        _ctext(draw, "{}°".format(g), gx + 2, gyv, display_font(12, 600), INK, anchor="lm")

    # nested ensemble band
    if has_band:
        def poly(los, his):
            return list(zip(xs, [Y(v) for v in his])) + list(zip(reversed(xs), [Y(v) for v in reversed(los)]))
        draw.polygon(poly([b[0] for b in bands], [b[3] for b in bands]), fill=BAND_OUT)
        draw.polygon(poly([b[1] for b in bands], [b[2] for b in bands]), fill=BAND_IN)

    # precip strip (grounded pop% bars, colored by kind)
    pbase = axis_y
    sc = bandh - 14
    for i, h in enumerate(hours):
        pop = h["pop"]
        if pop < 5:
            continue
        bx = xs[i]
        bw = (gw - 32) / n * 0.30
        bh = (pop / 100.0) * sc
        kind = weather.precip_kind(pop, h["precip_type"], h["thunder"])
        col = _KIND_BAR.get(kind, BLUE)
        draw.rectangle([bx - bw, pbase - bh, bx + bw, pbase], fill=col)
        _ctext(draw, "{}%".format(pop), bx, pbase - bh - 8, display_font(12, 600), col)
    _ctext(draw, "RAIN %", gx + 2, pbase - bandh + 2, display_font(10, 600), INK, anchor="lm")

    # temp line + points + labels + icons
    ys = [Y(t) for t in temps]
    draw.line(list(zip(xs, ys)), fill=INK, width=3, joint="curve")
    for i, h in enumerate(hours):
        x, y = xs[i], ys[i]
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=INK)
        _ctext(draw, "{}°".format(h["temp_f"]), x, y - 14, display_font(19, 600), temp_color(h["temp_f"]))
        if icons[i] is not None:
            img.paste(icons[i], (int(x - 14), int(top - 32)), icons[i])

    # x axis
    draw.line([lx, axis_y, gx + gw, axis_y], fill=INK, width=1)
    for i, h in enumerate(hours):
        _ctext(draw, h["ampm_label"], xs[i], axis_y + 8, display_font(12, 600), INK)


def render_display(hours, bands, hour_icons, cards, badge,
                   location_name, date_str, updated_str):
    """Compose the full 800x480 image. Returns an RGB PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw_graph(img, draw, hours, bands, hour_icons, 14, GRAPH_Y, WIDTH - 28, GRAPH_H)
    draw_banner(draw, cards)
    draw_header(draw, location_name, date_str, updated_str, badge)
    return img


def render_error(message):
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, 30], fill=RED)
    draw.text((10, 7), "Weather update failed", font=display_font(15, 600), fill=WHITE)
    _ctext(draw, message, WIDTH / 2, HEIGHT / 2, display_font(18, 600), INK)
    _ctext(draw, "Will retry next hour", WIDTH / 2, HEIGHT / 2 + 34, display_font(14, 600), INK)
    return img
