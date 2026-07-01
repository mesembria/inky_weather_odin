"""Pillow rendering for the Inky Impression weather display."""
from PIL import Image, ImageDraw, ImageFont

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
