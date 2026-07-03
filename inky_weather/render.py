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

ICON_SZ_HOUR = 34
ICON_SZ_DAY = 32

# --- new redesign palette + font (additive) ---
INK = (20, 22, 28)
PURPLE = (150, 40, 140)
GRAY = (120, 122, 130)
FAINT = (225, 226, 230)

ACCENTS = {"red": RED, "orange": ORANGE, "blue": BLUE, "green": GREEN,
           "purple": PURPLE, "ink": INK, "gray": GRAY}

_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Oswald.ttf")


def display_font(size, weight=600):
    """Bundled Oswald at the given size and weight (300 or 600)."""
    f = ImageFont.truetype(_FONT_PATH, int(size))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def kind_color(kind):
    """RGB for a precip kind name from weather.precip_kind()."""
    return {
        "rain": COLOR_RAIN,
        "storm": COLOR_STORM,
        "snow": COLOR_SNOW,
        "mix": COLOR_MIX,
        "dry": COLOR_DRY,
    }.get(kind, COLOR_RAIN)


def temp_color(temp_f):
    """Warm temps -> red, cool -> blue. Simple two-stop ramp."""
    if temp_f >= 78:
        return RED
    if temp_f >= 60:
        return BLACK
    return BLUE


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size):
    """Load a bold TrueType font at the given size, falling back to default."""
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_centered_text(draw, text, cx, cy, font, color):
    """Draw text horizontally centered on cx and vertically centered on cy."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), text, font=font, fill=color)


def draw_bolt(draw, x, y, size, color):
    """Draw a small lightning-bolt glyph in a size x size box at top-left (x, y).

    Used instead of the unicode bolt emoji, which the TrueType fonts don't cover.
    """
    w = h = size
    pts = [
        (x + 0.55 * w, y),
        (x + 0.20 * w, y + 0.55 * h),
        (x + 0.45 * w, y + 0.55 * h),
        (x + 0.30 * w, y + h),
        (x + 0.80 * w, y + 0.40 * h),
        (x + 0.52 * w, y + 0.40 * h),
        (x + 0.70 * w, y),
    ]
    draw.polygon(pts, fill=color)


# Layout geometry (pixels). Hourly zones (below header) sum to HEIGHT.
LAYOUT = {
    "header_h": 30,
    "temp_h": 250,
    "feels_h": 18,
    "precip_h": 80,
    "uv_h": 22,
    "hour_h": 80,          # 30+250+18+80+22+80 = 480
    "daily_w": 215,
    "hourly_w": WIDTH - 215,
    "num_hours": 12,
    "num_days": 10,
}
LAYOUT["strip_x"] = LAYOUT["hourly_w"] + 2
LAYOUT["strip_w"] = LAYOUT["daily_w"] - 2


def draw_header(draw, location_name, date_str, updated_str):
    """Draw the top header band: location - date (left), updated (center)."""
    L = LAYOUT
    draw.rectangle([0, 0, WIDTH, L["header_h"]], fill=BLACK)
    font = load_font(15)
    left = location_name + " · " + date_str if location_name else date_str
    draw.text((10, L["header_h"] / 2 - 8), left, font=font, fill=WHITE)
    updated = "Updated " + updated_str
    draw_centered_text(draw, updated, L["hourly_w"] / 2 + 120, L["header_h"] / 2,
                       load_font(12), (200, 200, 200))
    draw_centered_text(draw, "10-DAY FORECAST", L["hourly_w"] + L["daily_w"] / 2,
                       L["header_h"] / 2, load_font(11), (210, 210, 210))


def draw_hourly_panel(img, draw, hours, icons):
    """Draw the left hourly panel. `icons` is a list of RGBA images parallel to hours."""
    L = LAYOUT
    n = L["num_hours"]
    col_w = L["hourly_w"] / n
    temp_y = L["header_h"]
    feels_y = temp_y + L["temp_h"]
    precip_y = feels_y + L["feels_h"]
    uv_y = precip_y + L["precip_h"]
    hour_y = uv_y + L["uv_h"]

    temps = [h["temp_f"] for h in hours]
    min_t, max_t = min(temps), max(temps)
    t_range = (max_t - min_t) or 1

    small = load_font(12)
    tiny = load_font(11)
    pct_font = load_font(10)

    # Night shading (full panel height)
    for i, h in enumerate(hours):
        if not h["is_daytime"]:
            x0 = int(i * col_w)
            draw.rectangle([x0, L["header_h"], int(x0 + col_w), HEIGHT],
                           fill=(225, 227, 240))

    # Temperature graph: icon positioned by temp, label below
    icon_sz = ICON_SZ_HOUR
    usable = L["temp_h"] - icon_sz - 22
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        norm = (h["temp_f"] - min_t) / t_range
        icon_top = temp_y + usable * (1 - norm) + 4
        if icons[i] is not None:
            img.paste(icons[i], (int(cx - icon_sz / 2), int(icon_top)), icons[i])
        draw_centered_text(draw, "{}°".format(h["temp_f"]),
                           cx, icon_top + icon_sz + 10, small, temp_color(h["temp_f"]))

    # Feels-like row
    draw.line([0, feels_y, L["hourly_w"], feels_y], fill=(180, 180, 180))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        draw_centered_text(draw, "FL {}°".format(h["feels_f"]),
                           cx, feels_y + L["feels_h"] / 2, tiny, (100, 100, 100))

    # Precip probability bars
    draw.line([0, precip_y, L["hourly_w"], precip_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        bar_h = max(2, int((h["pop"] / 100) * (L["precip_h"] - 4)))
        bar_top = precip_y + L["precip_h"] - bar_h
        color = COLOR_STORM if h["thunder"] >= 30 else COLOR_RAIN
        draw.rectangle([int(i * col_w + 3), bar_top, int((i + 1) * col_w - 3),
                        precip_y + L["precip_h"]], fill=color)
        if h["pop"] > 0:
            draw_centered_text(draw, "{}%".format(h["pop"]), cx, bar_top + 8,
                               pct_font, WHITE)
        if h["thunder"] >= 30:
            draw_bolt(draw, cx - 5, precip_y + 3, 11, ORANGE)

    # UV row
    draw.line([0, uv_y, L["hourly_w"], uv_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        uv_col = RED if h["uv"] >= 6 else (GREEN if h["uv"] < 3 else ORANGE)
        draw_centered_text(draw, "UV {}".format(h["uv"]), cx, uv_y + L["uv_h"] / 2,
                           tiny, uv_col)

    # Hour labels
    draw.line([0, hour_y, L["hourly_w"], hour_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        draw_centered_text(draw, h["ampm_label"], cx, hour_y + 14, small, BLACK)

    # Vertical divider between panels
    draw.rectangle([L["hourly_w"], 0, L["hourly_w"] + 2, HEIGHT], fill=BLACK)


def _draw_precip_bar(draw, x, y, track_w, label, cell, font_tiny):
    """One horizontal precip bar: label, filled track (len=pop), %, pips."""
    kind = weather.precip_kind(cell["pop"], cell["precip_type"], cell["thunder"])
    color = kind_color(kind)
    track_h = 12
    draw.text((x, y + 1), label, font=font_tiny, fill=(120, 120, 120))
    tx = x + 12
    draw.rectangle([tx, y, tx + track_w, y + track_h], fill=(225, 221, 210))
    fill_w = int((cell["pop"] / 100) * track_w)
    if kind != "dry" and fill_w > 0:
        draw.rectangle([tx, y, tx + fill_w, y + track_h], fill=color)
    draw.text((tx + track_w - 26, y + 1), "{}%".format(cell["pop"]),
              font=font_tiny, fill=(70, 70, 70) if fill_w < track_w * 0.55 else WHITE)
    mx = tx + track_w + 4
    if cell["thunder"] >= 30:
        draw_bolt(draw, mx, y + 2, 10, ORANGE)
        mx += 12
    level = weather.intensity_level(cell["qpf_mm"], cell["pop"])
    for p in range(3):
        pc = color if p < level else (216, 210, 196)
        px = mx + p * 7
        draw.ellipse([px, y + 4, px + 4, y + 8], fill=pc)


def draw_daily_row(img, draw, day, y, row_h, icon, global_lo, global_hi):
    """Draw one day's row in the right strip."""
    L = LAYOUT
    strip_x = L["strip_x"]
    strip_w = L["strip_w"]
    tiny = load_font(11)
    micro = load_font(10)

    if icon is not None:
        img.paste(icon, (strip_x + 6, int(y + row_h / 2 - ICON_SZ_DAY // 2)), icon)
    draw_centered_text(draw, day["name"], strip_x + 20, y + row_h - 8, micro, BLACK)

    content_x = strip_x + 40
    content_w = strip_w - 42

    g_range = (global_hi - global_lo) or 1
    t_bar_x = content_x + 20
    t_bar_w = content_w - 40
    t_bar_y = y + 6
    t_bar_h = 8
    draw.text((content_x, t_bar_y - 1), "{}°".format(day["lo_f"]), font=micro, fill=BLUE)
    draw.rectangle([t_bar_x, t_bar_y, t_bar_x + t_bar_w, t_bar_y + t_bar_h], fill=(215, 215, 215))
    seg_l = int(((day["lo_f"] - global_lo) / g_range) * t_bar_w)
    seg_r = int(((day["hi_f"] - global_lo) / g_range) * t_bar_w)
    draw.rectangle([t_bar_x + seg_l, t_bar_y, t_bar_x + seg_r, t_bar_y + t_bar_h],
                   fill=temp_color(day["hi_f"]))
    draw.text((t_bar_x + t_bar_w + 3, t_bar_y - 1), "{}°".format(day["hi_f"]),
              font=micro, fill=RED)

    p_track_w = content_w - 70
    _draw_precip_bar(draw, content_x, y + 18, p_track_w, "D", day["day"], tiny)
    _draw_precip_bar(draw, content_x, y + 31, p_track_w, "N", day["night"], tiny)


def draw_daily_strip(img, draw, days, icons):
    """Draw all daily rows in the right strip using a shared temperature scale."""
    L = LAYOUT
    strip_x = L["strip_x"]
    strip_w = L["strip_w"]
    row_h = (HEIGHT - L["header_h"]) / len(days)
    global_lo = min(d["lo_f"] for d in days)
    global_hi = max(d["hi_f"] for d in days)
    for i, day in enumerate(days):
        y = int(L["header_h"] + i * row_h)
        if i > 0:
            draw.line([strip_x, y, strip_x + strip_w, y], fill=(205, 200, 186))
        draw_daily_row(img, draw, day, y, row_h, icons[i], global_lo, global_hi)


def render_error(message):
    """Render a simple full-screen error card so failures are visible on-panel."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, LAYOUT["header_h"]], fill=RED)
    draw.text((10, 7), "Weather update failed", font=load_font(15), fill=WHITE)
    draw_centered_text(draw, message, WIDTH / 2, HEIGHT / 2, load_font(18), BLACK)
    draw_centered_text(draw, "Will retry next hour", WIDTH / 2, HEIGHT / 2 + 34,
                       load_font(13), (110, 110, 110))
    return img


def render_display(hours, days, hour_icons, day_icons,
                   location_name, date_str, updated_str):
    """Compose the full 800x480 image. Returns an RGB PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw_hourly_panel(img, draw, hours, hour_icons)
    draw_daily_strip(img, draw, days, day_icons)
    draw_header(draw, location_name, date_str, updated_str)
    return img
