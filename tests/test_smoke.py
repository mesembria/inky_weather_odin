def test_pytest_runs():
    assert True


def test_optional_fetch_swallows_errors():
    from inky_weather import main
    assert main._safe(lambda: (_ for _ in ()).throw(RuntimeError("boom")), default="X") == "X"


def test_fixture_render_end_to_end(tmp_path):
    from PIL import Image
    from inky_weather import main
    # build_image raises on failure; main() would swallow it into an 800x480
    # error card, so assert on build_image directly for a real end-to-end check.
    img = main.build_image(True, {"location_name": "Blacksburg, VA"})
    assert img.size == (800, 480)
    # a successful render leaves the top-left white; the error card paints a red
    # banner there (RED = (200, 30, 30)), so this distinguishes the two.
    assert img.getpixel((5, 5)) != (200, 30, 30)
    # and the CLI path still writes an 800x480 PNG
    out = tmp_path / "out.png"
    main.main(["--fixture", "--out", str(out)])
    assert Image.open(out).size == (800, 480)


def test_fixture_synthesizes_cooler_day_trend():
    # fixture mode synthesizes a warmer "yesterday"; the synthesized inputs yield a
    # "Cooler day" TREND card. (The bundled hourly fixture is a stormy day, so on the
    # full banner hazards correctly outrank TREND — hence we assert the card contract.)
    from inky_weather import weather, advice, main
    _hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    today = {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]}
    yesterday = {"hi_f": days[0]["hi_f"] + 6, "lo_f": days[0]["lo_f"] + 4}
    result = advice._trend_card(today, yesterday, [d["hi_f"] for d in days[1:4]])
    assert result is not None
    assert result[1]["cat"] == "TREND" and result[1]["verdict"] == "Cooler day"


def test_trend_first_run_forward_uses_tomorrow():
    # No persisted history yet. The fixture window's high is already behind, so the
    # trend pivots to tomorrow-vs-today — available from the forecast alone.
    import datetime
    from inky_weather import weather, advice, main, history
    hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    trend = history.trend_input(days, {}, datetime.date(2026, 7, 7))
    forward = advice._today_high_passed(hours, trend["today"]["hi_f"])
    assert forward is True
    card = advice._trend_card(trend["today"], trend["yesterday"], trend["stretch_his"],
                              tomorrow=trend["tomorrow"], forward=forward)
    assert card is not None
    assert "tomorrow" in card[1]["detail"]


def test_gridlines_survive_seven_color_quantization():
    # The Inky Impression is a 7-color panel; main.py hands the RGB image to the inky
    # library, which quantizes it. A near-white gridline snaps to white and vanishes on
    # the panel even though it looks correct in the RGB PNG. Guard the color choice.
    from inky_weather import render

    PANEL = [(0, 0, 0), (255, 255, 255), (0, 255, 0), (0, 0, 255),
             (255, 0, 0), (255, 255, 0), (255, 140, 0)]

    def nearest(c):
        return min(PANEL, key=lambda p: sum((a - b) ** 2 for a, b in zip(p, c)))

    assert nearest(render.GRIDLINE) != (255, 255, 255)


def test_gridlines_are_dotted_not_solid():
    # "Faint" has to come from coverage, not lightness — there is no gray in the panel
    # palette. A solid black rule would read far too heavy.
    from PIL import Image, ImageDraw
    from inky_weather import render

    img = Image.new("RGB", (200, 20), render.PAPER)
    d = ImageDraw.Draw(img)
    render._dotted_line(d, 10, 190, 10, render.GRIDLINE)
    row = [img.getpixel((x, 10)) for x in range(10, 190)]
    on = sum(1 for p in row if p == render.GRIDLINE)
    assert on > 0                       # something is drawn
    assert on < len(row) * 0.5          # but it is not a solid rule


def test_precip_gridlines_and_caption_only_when_wet():
    from PIL import Image, ImageDraw
    from inky_weather import render

    W, H = render.WIDTH, render.HEIGHT
    axis_y = render.GRAPH_Y + render.GRAPH_H - 16   # matches draw_graph's axis_y
    sc = 82 - 14                                    # bandh - 14 (bar-band scale)
    y100, y50 = axis_y - sc, axis_y - int(sc * 0.5)  # 100% and 50% gridline rows
    # gridlines are dotted, so scan a span rather than probing a single pixel
    span = range(80, 130)   # on the full-width gridlines, clear of every bar column
    GRID = render.GRIDLINE

    def dots(img, y):
        return sum(1 for x in span if img.getpixel((x, y)) == GRID)

    def render_hours(pops):
        img = Image.new("RGB", (W, H), render.PAPER)
        d = ImageDraw.Draw(img)
        hours = [{"hour": 9 + i, "ampm_label": "9a", "is_daytime": True,
                  "condition": "CLEAR", "icon_uri": "", "temp_f": 70, "feels_f": 70,
                  "pop": p, "precip_type": "RAIN", "thunder": 0, "uv": 3}
                 for i, p in enumerate(pops)]
        render.draw_graph(img, d, hours, [], [None] * len(pops),
                          14, render.GRAPH_Y, W - 28, render.GRAPH_H)
        return img

    # wet: both reference lines are drawn, checked at a column clear of any bar
    wet = render_hours([0, 0, 0, 0, 0, 60, 0, 0, 0, 0, 0, 0])
    assert dots(wet, y100) > 0     # 100% line present
    assert dots(wet, y50) > 0      # 50% line present
    # dry: strip is completely clean — no lines, no caption, no bars
    dry = render_hours([0] * 12)
    assert dots(dry, y100) == 0
    assert dots(dry, y50) == 0
    for y in range(axis_y - sc - 2, axis_y - 1):
        for x in range(45, W - 20):
            assert dry.getpixel((x, y)) == render.PAPER


def test_precip_gridlines_gate_at_pop_boundary():
    from PIL import Image, ImageDraw
    from inky_weather import render

    W, H = render.WIDTH, render.HEIGHT
    axis_y = render.GRAPH_Y + render.GRAPH_H - 16
    y100 = axis_y - (82 - 14)
    GRID, span = render.GRIDLINE, range(80, 130)

    def gridline_present(pop):
        img = Image.new("RGB", (W, H), render.PAPER)
        d = ImageDraw.Draw(img)
        hours = [{"hour": 9 + i, "ampm_label": "9a", "is_daytime": True,
                  "condition": "CLEAR", "icon_uri": "", "temp_f": 70, "feels_f": 70,
                  "pop": pop, "precip_type": "RAIN", "thunder": 0, "uv": 3}
                 for i in range(12)]
        render.draw_graph(img, d, hours, [], [None] * 12,
                          14, render.GRAPH_Y, W - 28, render.GRAPH_H)
        return any(img.getpixel((x, y100)) == GRID for x in span)

    assert gridline_present(5) is True     # pop == 5 -> wet gate open, lines drawn
    assert gridline_present(4) is False    # pop == 4 -> strip stays clean
