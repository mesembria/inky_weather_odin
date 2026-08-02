from PIL import Image, ImageDraw
from inky_weather import render


def test_dimensions():
    assert render.WIDTH == 800
    assert render.HEIGHT == 480


def test_temp_color_hot_is_red_ish():
    r, g, b = render.temp_color(95)
    assert r > b


def _blank():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    return img, ImageDraw.Draw(img)


def test_draw_header_marks_top_band():
    img, d = _blank()
    render.draw_header(d, "Blacksburg, VA", "Tue Jun 30", "10:02 AM", ("HIGH", "green"))
    assert any(img.getpixel((x, 20)) != render.PAPER for x in range(0, render.WIDTH, 20))


def test_render_error_card_returns_image():
    img = render.render_error("No network: fetch failed")
    assert img.size == (render.WIDTH, render.HEIGHT)
    assert any(img.getpixel((x, render.HEIGHT // 2)) != render.PAPER
               for x in range(0, render.WIDTH, 10))


def test_display_font_loads_and_varies_weight():
    f = render.display_font(30, 600)
    assert hasattr(f, "getbbox")
    assert render.ACCENTS["red"] == render.RED


def test_draw_banner_marks_pixels():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
    d = ImageDraw.Draw(img)
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "63-81°", "accent": "orange"},
             {"cat": "STORMS", "verdict": "T-storms 2p", "detail": "65%", "accent": "red"}]
    render.draw_banner(d, cards)
    assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()


def test_draw_graph_runs_with_and_without_band():
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 20 * (i % 3), "precip_type": "RAIN", "thunder": 0, "uv": 3}
             for i in range(12)]
    bands = [(t - 3, t - 1, t + 1, t + 3) for t in (h["temp_f"] for h in hours)]
    for b in (bands, []):
        img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
        d = ImageDraw.Draw(img)
        render.draw_graph(img, d, hours, b, [None] * 12, 14, 160, render.WIDTH - 28, 300)
        assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()


def test_render_display_dimensions_with_and_without_band():
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 10, "precip_type": "RAIN", "thunder": 0, "uv": 3} for i in range(12)]
    bands = [(t - 3, t - 1, t + 1, t + 3) for t in (h["temp_f"] for h in hours)]
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "70-81°", "accent": "orange"}]
    for b in (bands, []):
        img = render.render_display(hours, b, [None] * 12, cards,
                                    ("HIGH CONFIDENCE", "green"), "Town", "Thu Jul 3", "2p")
        assert img.size == (800, 480)


def test_stamp_stale_marks_top_right_corner():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    out = render.stamp_stale(img)
    assert out.size == (render.WIDTH, render.HEIGHT)
    # The pill sits below the header rule in the top-right corner and is solid
    # RED (no anti-aliasing).
    assert any(out.getpixel((x, y)) == render.RED
               for x in range(render.WIDTH - 60, render.WIDTH)
               for y in range(render.HEADER_RULE_Y, render.HEADER_RULE_Y + 30))


def test_stamp_stale_leaves_center_untouched():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    render.stamp_stale(img)
    assert img.getpixel((render.WIDTH // 2, render.HEIGHT // 2)) == render.PAPER


def test_stamp_stale_does_not_cover_confidence_badge():
    # A real render carries a confidence badge in the header top-right (y~15).
    # Use a non-red accent so any exact-RED pixel in that band can only be the pill.
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 10, "precip_type": "RAIN", "thunder": 0, "uv": 3} for i in range(12)]
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "70-81°", "accent": "orange"}]
    img = render.render_display(hours, [], [None] * 12, cards,
                               ("HIGH CONFIDENCE", "green"), "Town", "Thu Jul 3", "2p")
    render.stamp_stale(img)
    badge_band = [img.getpixel((x, y))
                  for x in range(render.WIDTH - 60, render.WIDTH) for y in range(8, 22)]
    assert render.RED not in badge_band            # pill no longer overprints the badge row
    below_rule = [img.getpixel((x, y))
                  for x in range(render.WIDTH - 60, render.WIDTH)
                  for y in range(render.HEADER_RULE_Y, render.HEADER_RULE_Y + 30)]
    assert render.RED in below_rule                # pill is present just below the header rule


def test_updated_label_without_version():
    assert render._updated_label("9:08pm") == "9:08pm · NEXT 12H"


def test_updated_label_with_version():
    assert render._updated_label("9:08pm", "v1.0.0") == "9:08pm · NEXT 12H · v1.0.0"


def test_draw_header_renders_version_when_given():
    img1, d1 = _blank()
    render.draw_header(d1, "Town", "Tue Jun 30", "10:02 AM", None)
    img2, d2 = _blank()
    render.draw_header(d2, "Town", "Tue Jun 30", "10:02 AM", None, "v9.9.9")
    assert img1.tobytes() != img2.tobytes()   # version text is actually drawn
