import datetime
import os

from inky_weather import history


def test_load_history_missing_file_returns_empty(tmp_path):
    assert history.load_history(str(tmp_path / "nope.json")) == {}


def test_record_day_roundtrips(tmp_path):
    path = str(tmp_path / "hist.json")
    history.record_day(datetime.date(2026, 7, 7), 92, 63, path=path)
    hist = history.load_history(path)
    assert hist["2026-07-07"] == {"hi_f": 92, "lo_f": 63}


def test_record_day_prunes_to_keep(tmp_path):
    path = str(tmp_path / "hist.json")
    for d in range(1, 8):                       # 7 days, keep=3
        history.record_day(datetime.date(2026, 7, d), 80 + d, 60, path=path, keep=3)
    hist = history.load_history(path)
    assert sorted(hist) == ["2026-07-05", "2026-07-06", "2026-07-07"]


def test_record_day_swallows_write_errors(tmp_path):
    # a path whose parent is a file (not a dir) can't be written; must not raise
    bad_parent = tmp_path / "afile"
    bad_parent.write_text("x")
    history.record_day(datetime.date(2026, 7, 7), 90, 60, path=str(bad_parent / "h.json"))


def test_trend_input_assembles_today_yesterday_and_stretch():
    days = [{"hi_f": 88, "lo_f": 60}, {"hi_f": 91}, {"hi_f": 94}, {"hi_f": 90}]
    hist = {
        "2026-07-05": {"hi_f": 95, "lo_f": 62},
        "2026-07-06": {"hi_f": 93, "lo_f": 61},
        "2026-07-07": {"hi_f": 92, "lo_f": 63},   # yesterday relative to the 8th
    }
    ti = history.trend_input(days, hist, datetime.date(2026, 7, 8))
    assert ti["today"] == {"hi_f": 88, "lo_f": 60}
    assert ti["yesterday"] == {"hi_f": 92, "lo_f": 63}
    # 3 persisted past highs + 3 forecast forward highs, today excluded
    assert ti["stretch_his"] == [95, 93, 92, 91, 94, 90]


def test_trend_input_no_history_has_no_yesterday():
    days = [{"hi_f": 88, "lo_f": 60}, {"hi_f": 91}, {"hi_f": 94}, {"hi_f": 90}]
    ti = history.trend_input(days, {}, datetime.date(2026, 7, 8))
    assert ti["yesterday"] is None
    assert ti["stretch_his"] == [91, 94, 90]      # forward-only until history builds


def test_trend_input_none_without_days():
    assert history.trend_input([], {}, datetime.date(2026, 7, 8)) is None
