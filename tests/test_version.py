from unittest import mock

from inky_weather import version


def test_get_version_returns_stripped_stdout():
    cp = mock.Mock(stdout="v1.0.0\n")
    with mock.patch("inky_weather.version.subprocess.run", return_value=cp):
        assert version.get_version() == "v1.0.0"


def test_get_version_empty_stdout_returns_unknown():
    cp = mock.Mock(stdout="\n")
    with mock.patch("inky_weather.version.subprocess.run", return_value=cp):
        assert version.get_version() == "unknown"


def test_get_version_exception_returns_unknown():
    with mock.patch("inky_weather.version.subprocess.run",
                    side_effect=FileNotFoundError):
        assert version.get_version() == "unknown"
