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


def test_trend_absent_on_first_run():
    # no persisted history yet -> trend_input yields no yesterday -> no TREND card
    import datetime
    from inky_weather import weather, advice, main, history
    hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    trend = history.trend_input(days, {}, datetime.date(2026, 7, 7))
    cards = advice.build_cards(hours, [], [], [], {}, datetime.date(2026, 7, 7),
                               days=days, trend=trend)
    assert not any(c["cat"] == "TREND" for c in cards)
