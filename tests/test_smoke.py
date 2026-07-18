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


def test_precip_gridlines_and_caption_only_when_wet():
    from PIL import Image, ImageDraw
    from inky_weather import render

    W, H = render.WIDTH, render.HEIGHT
    axis_y = render.GRAPH_Y + render.GRAPH_H - 16   # matches draw_graph's axis_y

    def render_strip(pop):
        img = Image.new("RGB", (W, H), render.PAPER)
        d = ImageDraw.Draw(img)
        hours = [{"hour": 9 + i, "ampm_label": "9a", "is_daytime": True,
                  "condition": "CLEAR", "icon_uri": "", "temp_f": 70, "feels_f": 70,
                  "pop": pop, "precip_type": "RAIN", "thunder": 0, "uv": 3}
                 for i in range(12)]
        render.draw_graph(img, d, hours, [], [None] * 12,
                          14, render.GRAPH_Y, W - 28, render.GRAPH_H)
        return img

    def strip_has_marks(img):
        # scan the lower precip band (safely below any temperature gridline) for
        # any non-background pixel — gridlines, bars, or the caption.
        for y in range(axis_y - 60, axis_y - 1):
            for x in range(45, W - 20):
                if img.getpixel((x, y)) != render.PAPER:
                    return True
        return False

    assert strip_has_marks(render_strip(60)) is True    # wet: lines + bars present
    assert strip_has_marks(render_strip(0)) is False     # dry: strip completely clean
