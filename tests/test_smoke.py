def test_pytest_runs():
    assert True


def test_optional_fetch_swallows_errors():
    from inky_weather import main
    assert main._safe(lambda: (_ for _ in ()).throw(RuntimeError("boom")), default="X") == "X"
