def test_pytest_runs():
    assert True


def test_optional_fetch_swallows_errors():
    from inky_weather import main
    assert main._safe(lambda: (_ for _ in ()).throw(RuntimeError("boom")), default="X") == "X"


def test_fixture_render_end_to_end(tmp_path):
    from inky_weather import main
    out = tmp_path / "out.png"
    main.main(["--fixture", "--out", str(out)])
    from PIL import Image
    assert Image.open(out).size == (800, 480)
