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


def test_fixture_trend_card_present():
    # the bundled trend fixture loads into a window that yields a TREND card
    from inky_weather import weather, advice, main
    window = weather.load_trend_daily_fixture(main.FIXTURE_DIR)
    result = advice._trend_card(window)
    assert result is not None
    assert result[1]["cat"] == "TREND"


def test_fixture_trend_absent_on_missing_data():
    import datetime
    from inky_weather import weather, advice, main
    hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    cards = advice.build_cards(hours, [], [], [], {}, datetime.date(2026, 7, 7),
                               days=days, trend=[])
    assert not any(c["cat"] == "TREND" for c in cards)
