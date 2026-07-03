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
