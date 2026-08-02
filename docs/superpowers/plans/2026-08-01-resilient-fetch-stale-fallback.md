# Resilient Fetch + Stale-Image Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Absorb transient connection failures with bounded retries, and on total failure re-show the last-good render with a small "STALE" pill instead of a full-screen error card.

**Architecture:** Add a connection-only retry helper to `weather.fetch_live`; cache each successful RGB render to disk; on any build failure, reload that cached image, stamp a corner pill, and push it — falling back to the existing error card only when no cache exists. The Inky panel is e-ink, so the cached image is a faithful last-hour view.

**Tech Stack:** Python 3.13, `requests`, Pillow (PIL) 12.3.0, pytest with `unittest.mock`.

## Global Constraints

- Retries apply ONLY to `weather.fetch_live` (the primary Google call). The four `_safe()`-wrapped supplementary fetches keep their current one-shot behavior.
- Retry ONLY on `requests.exceptions.ConnectionError` and `requests.exceptions.Timeout`. Never retry HTTP status errors (`WeatherAPIError`) or any other exception.
- Retry defaults: `attempts=5`, `backoff=2.0` → sleeps of 2, 4, 8, 16s between the 5 attempts.
- Cache and fallback are LIVE-only. Fixture runs (`--fixture`) never read or write the cache.
- All disk writes are best-effort, atomic (`tmp` + `os.replace`), mirroring `history.py`.
- Colors are exact RGB constants from `render.py`: `RED = (200, 30, 30)`, `WHITE = (255, 255, 255)`, `PAPER = (255, 255, 255)`.
- Tests live in `tests/`, one file per module, using `unittest.mock` and `mock.patch("inky_weather.weather.requests.get", ...)` patterns already established in `tests/test_weather.py`.
- Run tests with the repo's pytest config: `.venv/bin/python -m pytest` (the `-p no:debugging` flag is set in `pytest.ini`).

---

### Task 1: Connection-only retry helper in `weather.py`

**Files:**
- Modify: `inky_weather/weather.py` (add `import time`; add `_get_with_retries`; route `fetch_live`'s two GETs through it, lines 105-114)
- Test: `tests/test_weather.py`

**Interfaces:**
- Produces: `weather._get_with_retries(url, timeout, attempts=5, backoff=2.0, sleep=None) -> requests.Response` — returns the first successful response; retries only on `ConnectionError`/`Timeout`; re-raises the last exception after `attempts` tries. `sleep=None` uses `time.sleep`, resolved at call time so tests can patch `weather.time.sleep`.
- Consumes: existing `weather.hourly_url`, `weather.daily_url`, `weather._raise_for_api_error`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_weather.py` (the file already has `from unittest import mock` and `import pytest`; add `import requests` near the top imports if not present):

```python
def test_get_with_retries_returns_after_transient_failures():
    resp = mock.Mock(ok=True)
    slept = []
    get = mock.Mock(side_effect=[
        requests.exceptions.ConnectionError("boom"),
        requests.exceptions.ConnectionError("boom"),
        resp,
    ])
    with mock.patch("inky_weather.weather.requests.get", get):
        out = weather._get_with_retries("http://x", timeout=1,
                                        sleep=lambda s: slept.append(s))
    assert out is resp
    assert slept == [2, 4]


def test_get_with_retries_exhausts_and_reraises():
    slept = []
    get = mock.Mock(side_effect=requests.exceptions.ConnectionError("down"))
    with mock.patch("inky_weather.weather.requests.get", get):
        with pytest.raises(requests.exceptions.ConnectionError):
            weather._get_with_retries("http://x", timeout=1,
                                      sleep=lambda s: slept.append(s))
    assert get.call_count == 5
    assert slept == [2, 4, 8, 16]


def test_get_with_retries_does_not_retry_other_errors():
    slept = []
    get = mock.Mock(side_effect=ValueError("nope"))
    with mock.patch("inky_weather.weather.requests.get", get):
        with pytest.raises(ValueError):
            weather._get_with_retries("http://x", timeout=1,
                                      sleep=lambda s: slept.append(s))
    assert get.call_count == 1
    assert slept == []


def test_fetch_live_retries_transient_then_succeeds():
    hourly = mock.Mock(ok=True)
    hourly.json.return_value = {"forecastHours": []}
    daily = mock.Mock(ok=True)
    daily.json.return_value = {"forecastDays": []}
    get = mock.Mock(side_effect=[
        requests.exceptions.ConnectionError("blip"),
        hourly,
        daily,
    ])
    with mock.patch("inky_weather.weather.requests.get", get):
        with mock.patch("inky_weather.weather.time.sleep", lambda s: None):
            hours, days = weather.fetch_live("40.0", "-105.1", "KEY")
    assert hours == [] and days == []
    assert get.call_count == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_weather.py -k "retries or retry" -v`
Expected: FAIL — `AttributeError: module 'inky_weather.weather' has no attribute '_get_with_retries'` (and `fetch_live` test fails because it currently calls `requests.get` directly with no retry).

- [ ] **Step 3: Add the retry helper and route `fetch_live` through it**

In `inky_weather/weather.py`, add `import time` to the imports block (top of file, alongside `import datetime`, `import json`, `import os`):

```python
import time
```

Add the helper just above `fetch_live` (after the `_raise_for_api_error` function, ~line 103):

```python
def _get_with_retries(url, timeout, attempts=5, backoff=2.0, sleep=None):
    """GET `url`, retrying only on connection-level failures.

    Retries on requests' ConnectionError/Timeout (the "Max retries exceeded"
    case) with exponential backoff (2, 4, 8, 16s across 5 attempts). Any other
    exception propagates immediately, and the last connection error is re-raised
    once attempts are exhausted. `sleep` is injectable so tests don't wait; when
    None it resolves time.sleep at call time (so tests can patch weather.time.sleep).
    """
    sleeper = sleep or time.sleep
    for attempt in range(attempts):
        try:
            return requests.get(url, timeout=timeout)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            if attempt == attempts - 1:
                raise
            sleeper(backoff * (2 ** attempt))
```

Replace the two `requests.get(...)` calls in `fetch_live` (lines 107 and 109) with `_get_with_retries(...)`:

```python
def fetch_live(lat, long, key, hours=12, days=10, timeout=20):
    """Fetch and parse both forecasts from the live API. Returns (hours, days)."""
    hourly_resp = _get_with_retries(hourly_url(lat, long, key, hours), timeout)
    _raise_for_api_error(hourly_resp)
    daily_resp = _get_with_retries(daily_url(lat, long, key, days), timeout)
    _raise_for_api_error(daily_resp)
    return (
        parse_hourly(hourly_resp.json(), count=hours),
        parse_daily(daily_resp.json(), count=days),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_weather.py -v`
Expected: PASS (new retry tests plus all pre-existing `weather` tests, including `test_fetch_live_raises_weather_api_error_with_message`, which still passes because a 400 flows through `_raise_for_api_error` unretried).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: retry live weather fetch on connection failures"
```

---

### Task 2: Last-good render cache module

**Files:**
- Create: `inky_weather/cache.py`
- Modify: `.gitignore` (add the runtime cache artifact)
- Test: `tests/test_cache.py`

**Interfaces:**
- Produces: `cache.save_display(img, path=cache.DEFAULT_PATH) -> None` (best-effort atomic PNG write) and `cache.load_display(path=cache.DEFAULT_PATH) -> PIL.Image.Image | None` (RGB image, or `None` if missing/unreadable).
- Produces: `cache.DEFAULT_PATH` — `inky_weather/last_display.png`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cache.py`:

```python
import os

from PIL import Image

from inky_weather import cache


def _img(color):
    return Image.new("RGB", (800, 480), color)


def test_save_then_load_roundtrips(tmp_path):
    path = os.path.join(tmp_path, "last.png")
    cache.save_display(_img((10, 20, 30)), path)
    loaded = cache.load_display(path)
    assert loaded is not None
    assert loaded.size == (800, 480)
    assert loaded.getpixel((0, 0)) == (10, 20, 30)


def test_load_missing_returns_none(tmp_path):
    assert cache.load_display(os.path.join(tmp_path, "nope.png")) is None


def test_load_unreadable_returns_none(tmp_path):
    path = os.path.join(tmp_path, "garbage.png")
    with open(path, "wb") as f:
        f.write(b"not a real png")
    assert cache.load_display(path) is None


def test_default_path_points_at_package():
    assert cache.DEFAULT_PATH.endswith(os.path.join("inky_weather", "last_display.png"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inky_weather.cache'`.

- [ ] **Step 3: Create the cache module**

Create `inky_weather/cache.py`:

```python
"""Persist the last successful render so a failed fetch can re-show it (stale).

The Inky Impression is e-ink and holds its last image, but a failed hourly run
still needs the pixels to re-push with a staleness marker. Mirrors history.py:
atomic tmp + os.replace, best-effort, stored beside this package.
"""
import os

from PIL import Image

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "last_display.png")


def save_display(img, path=DEFAULT_PATH):
    """Persist the last-good RGB render (pre-quantization). Best-effort."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        img.save(tmp, "PNG")
        os.replace(tmp, path)
    except OSError:
        pass


def load_display(path=DEFAULT_PATH):
    """Return the cached image as an RGB PIL Image, or None if unavailable."""
    try:
        with Image.open(path) as im:
            return im.convert("RGB")
    except (OSError, ValueError):
        return None
```

Add to `.gitignore` (after the existing `inky_weather/daily_history.json` line):

```
inky_weather/last_display.png
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cache.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/cache.py tests/test_cache.py .gitignore
git commit -m "feat: cache last-good render to disk"
```

---

### Task 3: Stale pill in `render.py`

**Files:**
- Modify: `inky_weather/render.py` (add `stamp_stale` after `render_error`, ~line 221)
- Test: `tests/test_render.py`

**Interfaces:**
- Produces: `render.stamp_stale(img) -> PIL.Image.Image` — draws a small `STALE` pill in the top-right corner using `RED`/`WHITE`/`display_font`, returns the same image object.
- Consumes: existing `render.WIDTH`, `render.RED`, `render.WHITE`, `render.display_font`, `render._ctext`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py`:

```python
def test_stamp_stale_marks_top_right_corner():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    out = render.stamp_stale(img)
    assert out.size == (render.WIDTH, render.HEIGHT)
    # The pill sits in the top-right corner and is solid RED (no anti-aliasing).
    assert any(out.getpixel((x, y)) == render.RED
               for x in range(render.WIDTH - 60, render.WIDTH)
               for y in range(0, 30))


def test_stamp_stale_leaves_center_untouched():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    render.stamp_stale(img)
    assert img.getpixel((render.WIDTH // 2, render.HEIGHT // 2)) == render.PAPER
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -k stamp_stale -v`
Expected: FAIL — `AttributeError: module 'inky_weather.render' has no attribute 'stamp_stale'`.

- [ ] **Step 3: Implement `stamp_stale`**

Add to `inky_weather/render.py`, right after `render_error` (~line 221):

```python
def stamp_stale(img):
    """Draw a small 'STALE' pill in the top-right corner; return the image.

    The cached render already shows its original update time in the header, so
    the pill only has to flag that the data is old, not when it was fetched.
    """
    draw = ImageDraw.Draw(img)
    font = display_font(14, 600)
    label = "STALE"
    pad_x, pad_y, margin = 8, 4, 6
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    pw = (right - left) + 2 * pad_x
    ph = (bottom - top) + 2 * pad_y
    x0 = WIDTH - margin - pw
    y0 = margin
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=RED)
    _ctext(draw, label, x0 + pw / 2, y0 + ph / 2, font, WHITE)
    return img
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: PASS (new stale tests plus all pre-existing render tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add STALE corner pill for cached renders"
```

---

### Task 4: Wire cache save + stale fallback into `main.py`

**Files:**
- Modify: `inky_weather/main.py` (import `cache`, line 7; save on live success and stale-fallback in `main()`, lines 95-116)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `cache.save_display`, `cache.load_display` (Task 2); `render.stamp_stale` (Task 3); existing `main.build_image`, `main._load_config`, `render.render_error`.
- Produces: no new public functions — behavior change to `main.main(argv)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_smoke.py`:

```python
def test_main_saves_cache_on_live_success(tmp_path, monkeypatch):
    from PIL import Image
    from inky_weather import main, render
    saved = []
    monkeypatch.setattr(main, "_load_config", lambda: {"location_name": "T"})
    monkeypatch.setattr(main, "build_image",
                        lambda use_fixture, cfg: Image.new("RGB", (800, 480), render.PAPER))
    monkeypatch.setattr(main.cache, "save_display",
                        lambda img, *a, **k: saved.append(img))
    out = tmp_path / "o.png"
    main.main(["--out", str(out)])
    assert len(saved) == 1


def test_main_skips_cache_on_fixture(tmp_path, monkeypatch):
    from inky_weather import main
    saved = []
    monkeypatch.setattr(main.cache, "save_display",
                        lambda img, *a, **k: saved.append(img))
    out = tmp_path / "o.png"
    main.main(["--fixture", "--out", str(out)])
    assert saved == []


def test_main_stale_fallback_when_cache_present(tmp_path, monkeypatch):
    from PIL import Image
    from inky_weather import main, render
    monkeypatch.setattr(main, "_load_config", lambda: {"location_name": "T"})
    def boom(use_fixture, cfg):
        raise RuntimeError("network down")
    monkeypatch.setattr(main, "build_image", boom)
    monkeypatch.setattr(main.cache, "load_display",
                        lambda *a, **k: Image.new("RGB", (800, 480), render.PAPER))
    out = tmp_path / "o.png"
    main.main(["--out", str(out)])
    img = Image.open(out).convert("RGB")
    # Stale pill present in the top-right...
    assert any(img.getpixel((x, y)) == render.RED
               for x in range(render.WIDTH - 60, render.WIDTH) for y in range(0, 30))
    # ...and it's NOT the error card (center stays PAPER).
    assert img.getpixel((render.WIDTH // 2, render.HEIGHT // 2)) == render.PAPER


def test_main_error_card_when_no_cache(tmp_path, monkeypatch):
    from PIL import Image
    from inky_weather import main, render
    monkeypatch.setattr(main, "_load_config", lambda: {"location_name": "T"})
    def boom(use_fixture, cfg):
        raise RuntimeError("network down")
    monkeypatch.setattr(main, "build_image", boom)
    monkeypatch.setattr(main.cache, "load_display", lambda *a, **k: None)
    out = tmp_path / "o.png"
    main.main(["--out", str(out)])
    img = Image.open(out).convert("RGB")
    # Error card draws content across the center row.
    assert any(img.getpixel((x, render.HEIGHT // 2)) != render.PAPER
               for x in range(0, render.WIDTH, 10))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_smoke.py -k "main_" -v`
Expected: FAIL — `AttributeError: module 'inky_weather.main' has no attribute 'cache'` (import not yet added; save/fallback wiring not present).

- [ ] **Step 3: Wire `cache` into `main.py`**

Update the import line (line 7):

```python
from . import weather, icons, render, advice, history, cache
```

Replace the body of `main()` from the `try:` block through the `except` (lines 103-110) with:

```python
    use_fixture = args.fixture
    try:
        if use_fixture:
            cfg = {"location_name": "Blacksburg, VA"}
        else:
            cfg = _load_config()
        img = build_image(use_fixture, cfg)
        if not use_fixture:
            cache.save_display(img)          # best-effort; keep last-good on disk
    except Exception as exc:  # keep last-good forecast up rather than a blank error
        cached = None if use_fixture else cache.load_display()
        if cached is not None:
            img = render.stamp_stale(cached)
        else:
            img = render.render_error(str(exc)[:80])
```

(The `if args.out:` / `else: push_to_display(img)` tail below stays unchanged.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_smoke.py -v`
Expected: PASS (4 new `main_` tests plus all pre-existing smoke tests, including `test_fixture_render_end_to_end`).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: PASS — entire suite green.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/main.py tests/test_smoke.py
git commit -m "feat: keep last-good render with STALE marker when fetch fails"
```

---

## Notes for the implementer

- **Why `--out` in the `main()` tests:** `main()` only calls `push_to_display` (a Pi-only import) in the non-`--out` branch. Every test uses `--out` so nothing touches hardware.
- **Why center-pixel checks discriminate stale vs error:** `render_error` writes text across the vertical center; `stamp_stale` touches only the top-right corner. A PAPER center means the stale path ran; a marked center means the error card ran.
- **`rounded_rectangle`** is available in the installed Pillow (12.3.0). If you ever target an older Pillow (<8.2), swap it for `draw.rectangle`.
