"""Pillow rendering for the Inky Impression weather display."""
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

    # Night shading (full panel height)
    for i, h in enumerate(hours):
        if not h["is_daytime"]:
            x0 = int(i * col_w)
            draw.rectangle([x0, L["header_h"], int(x0 + col_w), HEIGHT],
                           fill=(225, 227, 240))

    # Temperature graph: icon positioned by temp, label below
    icon_sz = 34
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
        color = COLOR_STORM if h["thunder"] > 30 else COLOR_RAIN
        draw.rectangle([int(i * col_w + 3), bar_top, int((i + 1) * col_w - 3),
                        precip_y + L["precip_h"]], fill=color)
        if h["pop"] > 0:
            draw_centered_text(draw, "{}%".format(h["pop"]), cx, bar_top + 8,
                               load_font(10), WHITE)
        if h["thunder"] >= 30:
            draw_centered_text(draw, "⚡", cx, precip_y + 8, load_font(12), YELLOW)

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
