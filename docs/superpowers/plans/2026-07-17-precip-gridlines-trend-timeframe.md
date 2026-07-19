# Precip Gridlines & Trend-Card Timeframe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the precip bars readable against a 0–100% scale, and make the TREND card state its timeframe — flipping from "today vs yesterday" to "tomorrow vs today" once today's high has passed.

**Architecture:** Two independent changes. (1) `render.py::draw_graph` gains two faint reference gridlines in the precip strip, gated on there being any rain chance. (2) `advice.py::_trend_card` names both compared days in its detail line and pivots forward using a data-driven "has today's high passed?" proxy (`advice._today_high_passed`) fed from the existing hourly window and Google daily high — no new API calls. Supporting data (`tomorrow`) threads through `history.trend_input` and `main.build_image`'s fixture branch.

**Tech Stack:** Python 3.13, Pillow (PIL) for rendering, pytest. Google Weather API (daily + hourly), already parsed in `weather.py`.

## Global Constraints

- All trend temps stay Google-sourced (daily `hi_f`/`lo_f`, hourly `temp_f`) — never cross-source, to keep the card bias-free and consistent with the rest of the display.
- Precip gridline color is the existing faint gray `(230, 231, 236)` (same as temp gridlines), width 1; lines only, no numeric level markers.
- Gridlines and the `"RAIN %"` caption appear **only** when `any(h["pop"] >= 5 for h in hours)`.
- Trend verdict words are unchanged (`Steady` / `Warmer day` / `Cooler day` / `Much warmer` / `Much cooler` / `Coolest stretch` / `Warmest stretch`); the detail line carries the timeframe.
- `TREND_HIGH_REACHED_TOL = 1` (°F) tolerance for "remaining window still reaches the daily high".
- Run tests with `python -m pytest` from the repo root.

---

## File Structure

- `inky_weather/render.py` — precip gridlines (Change 1).
- `inky_weather/advice.py` — trend detail rewrite, `_trend_verdict`, `_today_high_passed`, `build_cards` wiring (Change 2).
- `inky_weather/history.py` — `trend_input` adds `tomorrow`.
- `inky_weather/main.py` — fixture branch adds synthetic `tomorrow` + updated comment.
- `tests/test_smoke.py` — precip gridline render test; updated trend first-run test.
- `tests/test_advice.py` — updated trend detail assertions; forward-pivot + `_today_high_passed` tests.
- `tests/test_history.py` — `trend_input` tomorrow assertions.

---

## Task 1: Precip strip reference gridlines

**Files:**
- Modify: `inky_weather/render.py:153-167` (the precip strip block inside `draw_graph`)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `render.draw_graph(img, draw, hours, bands, icons, gx, gy, gw, gh)`, `render.WIDTH`, `render.HEIGHT`, `render.GRAPH_Y`, `render.GRAPH_H`, `render.PAPER`.
- Produces: no new symbols; behavior change only (gridlines + gated caption).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_smoke.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py::test_precip_gridlines_and_caption_only_when_wet -v`
Expected: FAIL — the dry case currently draws the always-on `"RAIN %"` caption, so `strip_has_marks(render_strip(0))` is `True`, not `False`.

- [ ] **Step 3: Implement the gate + gridlines**

In `inky_weather/render.py`, replace the precip strip block (currently lines 153-167):

```python
    # precip strip (grounded pop% bars, colored by kind)
    pbase = axis_y
    sc = bandh - 14
    for i, h in enumerate(hours):
        pop = h["pop"]
        if pop < 5:
            continue
        bx = xs[i]
        bw = (gw - 32) / n * 0.30
        bh = (pop / 100.0) * sc
        kind = weather.precip_kind(pop, h["precip_type"], h["thunder"])
        col = _KIND_BAR.get(kind, BLUE)
        draw.rectangle([bx - bw, pbase - bh, bx + bw, pbase], fill=col)
        _ctext(draw, "{}%".format(pop), bx, pbase - bh - 8, display_font(12, 600), col)
    _ctext(draw, "RAIN %", gx + 2, pbase - bandh + 2, display_font(10, 600), INK, anchor="lm")
```

with:

```python
    # precip strip (grounded pop% bars, colored by kind)
    pbase = axis_y
    sc = bandh - 14
    wet = any(h["pop"] >= 5 for h in hours)
    if wet:
        # faint 50% + 100% reference lines so each bar reads against its ceiling
        for frac in (0.5, 1.0):
            gyv = pbase - sc * frac
            draw.line([lx, gyv, gx + gw, gyv], fill=(230, 231, 236), width=1)
    for i, h in enumerate(hours):
        pop = h["pop"]
        if pop < 5:
            continue
        bx = xs[i]
        bw = (gw - 32) / n * 0.30
        bh = (pop / 100.0) * sc
        kind = weather.precip_kind(pop, h["precip_type"], h["thunder"])
        col = _KIND_BAR.get(kind, BLUE)
        draw.rectangle([bx - bw, pbase - bh, bx + bw, pbase], fill=col)
        _ctext(draw, "{}%".format(pop), bx, pbase - bh - 8, display_font(12, 600), col)
    if wet:
        _ctext(draw, "RAIN %", gx + 2, pbase - bandh + 2, display_font(10, 600), INK, anchor="lm")
```

(The gridlines are drawn **before** the bars so the colored fill and `%` labels render on top. `lx`, `gx`, `gw`, `pbase`, `sc` are already in scope.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS (new test + existing `test_fixture_render_end_to_end`).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_smoke.py
git commit -m "feat: add gated 50/100% precip reference gridlines

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Trend card — timeframe detail + forward pivot branch

Rewrite `_trend_card` so the detail line names both days and the comparison pivots forward when `forward=True`. New signature adds `tomorrow` and `forward` as keyword args with defaults, so `build_cards` and every existing test call keep working unchanged until Task 3 wires the pivot in.

**Files:**
- Modify: `inky_weather/advice.py:11-16` (constants), `inky_weather/advice.py:80-126` (`_trend_card`)
- Test: `tests/test_advice.py`

**Interfaces:**
- Consumes: `advice._card`, constants `TREND_HI_FLAT`, `TREND_HI_BIG`, `TREND_WINDOW_MARGIN`, `TREND_SCORE`.
- Produces:
  - `advice._trend_verdict(dhi) -> (verdict: str, accent: str)`
  - `advice._trend_card(today, yesterday, stretch_his, tomorrow=None, forward=False) -> (score, card) | None`
  - `today`/`yesterday`/`tomorrow` are `{"hi_f": int, "lo_f": int}` or `None`; `stretch_his` is `list[int]`.

- [ ] **Step 1: Update existing detail assertions + add forward tests (failing)**

In `tests/test_advice.py`, change these existing assertions to the new detail format:

```python
def test_trend_card_cooler_day():
    s, c = advice._trend_card(_t(78, 58), _t(85, 65), [])
    assert s == advice.TREND_SCORE and c["cat"] == "TREND"
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"
    assert c["detail"] == "today 78° · 7° cooler than yesterday"


def test_trend_card_drops_low_delta():
    # the low-delta append is gone; only the high framing remains
    s, c = advice._trend_card(_t(78, 58), _t(85, 63), [])
    assert c["detail"] == "today 78° · 7° cooler than yesterday"
    assert "low" not in c["detail"]


def test_trend_card_steady_when_flat():
    s, c = advice._trend_card(_t(80), _t(80), [])
    assert c["verdict"] == "Steady" and c["accent"] == "gray"
    assert c["detail"] == "today 80° · same as yesterday"


def test_trend_card_much_warmer():
    s, c = advice._trend_card(_t(76, 56), _t(64, 44), [])
    assert c["verdict"] == "Much warmer" and c["accent"] == "orange"
    assert c["detail"] == "today 76° · 12° warmer than yesterday"


def test_trend_card_coolest_stretch_upgrade():
    s, c = advice._trend_card(_t(70), _t(72), [84, 85, 86, 80])
    assert c["verdict"] == "Coolest stretch" and c["accent"] == "blue"
    assert c["detail"] == "today 70° · coolest day this week"


def test_trend_card_warmest_stretch_upgrade():
    s, c = advice._trend_card(_t(90), _t(80), [76, 73, 71, 80])
    assert c["verdict"] == "Warmest stretch" and c["accent"] == "orange"
    assert c["detail"] == "today 90° · warmest day this week"
```

(The old `test_trend_card_appends_low_when_it_moves` is replaced by `test_trend_card_drops_low_delta` above — delete the old one.)

Add new forward-branch tests:

```python
def test_trend_card_forward_tomorrow_warmer():
    s, c = advice._trend_card(_t(70), _t(72), [], tomorrow=_t(75), forward=True)
    assert c["verdict"] == "Warmer day" and c["accent"] == "orange"
    assert c["detail"] == "tomorrow 75° · 5° warmer than today"


def test_trend_card_forward_tomorrow_cooler():
    s, c = advice._trend_card(_t(80), _t(78), [], tomorrow=_t(74), forward=True)
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"
    assert c["detail"] == "tomorrow 74° · 6° cooler than today"


def test_trend_card_forward_steady():
    s, c = advice._trend_card(_t(80), _t(70), [], tomorrow=_t(80), forward=True)
    assert c["verdict"] == "Steady"
    assert c["detail"] == "tomorrow 80° · same as today"


def test_trend_card_forward_none_without_tomorrow():
    assert advice._trend_card(_t(80), _t(70), [], tomorrow=None, forward=True) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_advice.py -k trend -v`
Expected: FAIL — new detail strings don't match the old `"high 78° (-7)…"` format; forward tests hit the old 3-arg signature / branch that doesn't exist yet.

- [ ] **Step 3: Rewrite the constants + `_trend_card`**

In `inky_weather/advice.py`, delete the now-unused `TREND_LOW_DETAIL` constant (line 13: `TREND_LOW_DETAIL = 5 ...`). Then replace `_trend_card` (lines 80-126) with:

```python
def _trend_verdict(dhi):
    """(verdict, accent) for a day-over-day high change `dhi` (°F)."""
    if dhi <= -TREND_HI_BIG:
        return "Much cooler", "blue"
    if dhi <= -(TREND_HI_FLAT + 1):
        return "Cooler day", "blue"
    if dhi >= TREND_HI_BIG:
        return "Much warmer", "orange"
    if dhi >= TREND_HI_FLAT + 1:
        return "Warmer day", "orange"
    return "Steady", "gray"


def _trend_card(today, yesterday, stretch_his, tomorrow=None, forward=False):
    """Day-over-day TREND card, Google-sourced, with a peak/dip upgrade.

    Before today's high is reached the card compares today vs yesterday; once it
    has passed (`forward=True`) it flips to tomorrow vs today so the day-scale
    trend stays relevant late in the day. The detail line names both days.

      today/yesterday/tomorrow: {"hi_f","lo_f"} (yesterday/tomorrow may be None).
      stretch_his: highs of the surrounding days, EXCLUDING today; peak/dip only.
      forward: True once today's high is behind us (see _today_high_passed).
    Returns (score, card), or None when the needed neighbor day is missing.
    """
    if not today:
        return None
    hi = today["hi_f"]
    # window upgrade: today a strict peak/dip of the surrounding stretch by margin.
    # Needs >= 4 surrounding days so a pure-forecast run doesn't masquerade as a
    # "stretch" (that overlaps OUTLOOK) — it engages once past history builds up.
    if len(stretch_his) >= 4:
        if hi < min(stretch_his) and min(stretch_his) - hi >= TREND_WINDOW_MARGIN:
            return (TREND_SCORE, _card("TREND", "Coolest stretch",
                                       "today {}° · coolest day this week".format(hi), "blue"))
        if hi > max(stretch_his) and hi - max(stretch_his) >= TREND_WINDOW_MARGIN:
            return (TREND_SCORE, _card("TREND", "Warmest stretch",
                                       "today {}° · warmest day this week".format(hi), "orange"))
    # default: day-over-day, pivoting to tomorrow once today's high has passed
    if forward:
        if not tomorrow:
            return None
        ref, base, ref_hi = "tomorrow", "today", tomorrow["hi_f"]
        dhi = tomorrow["hi_f"] - hi
    else:
        if not yesterday:
            return None
        ref, base, ref_hi = "today", "yesterday", hi
        dhi = hi - yesterday["hi_f"]
    verdict, accent = _trend_verdict(dhi)
    if verdict == "Steady":
        detail = "{} {}° · same as {}".format(ref, ref_hi, base)
    else:
        word = "warmer" if dhi > 0 else "cooler"
        detail = "{} {}° · {}° {} than {}".format(ref, ref_hi, abs(dhi), word, base)
    return (TREND_SCORE, _card("TREND", verdict, detail, accent))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_advice.py -v`
Expected: PASS. All trend detail + forward tests green; `build_cards`/OUTLOOK tests unaffected (the 3-arg calls default `forward=False`).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: name both days in trend detail; add forward-pivot branch

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Data-driven pivot — `_today_high_passed` + `build_cards` wiring

**Files:**
- Modify: `inky_weather/advice.py` (add constant + helper near the other trend code; update `build_cards` at lines 279-282)
- Test: `tests/test_advice.py`

**Interfaces:**
- Consumes: `_trend_card(..., tomorrow=, forward=)` from Task 2; the `hours` list already passed to `build_cards` (each item has `"hour"` and `"temp_f"`); `trend` dict with `"today"` (and optional `"tomorrow"`).
- Produces: `advice._today_high_passed(hours, today_hi) -> bool` and constant `advice.TREND_HIGH_REACHED_TOL = 1`.

- [ ] **Step 1: Extend the `_trend` helper; adjust one build_cards test; add pivot + helper tests (failing)**

In `tests/test_advice.py`, extend the `_trend` helper to carry `tomorrow`:

```python
def _trend(today, yesterday, stretch_his, tomorrow=None):
    return {"today": today, "yesterday": yesterday,
            "tomorrow": tomorrow, "stretch_his": stretch_his}
```

`test_build_cards_includes_trend` currently uses hours whose max (71°) is below `today_hi` (78°); once `build_cards` computes `forward` that would flip it to the forward branch (no tomorrow → no card). Keep it exercising the morning branch by giving it hours that reach the high:

```python
def test_build_cards_includes_trend():
    hrs = _hours([70, 73, 76, 78, 77, 75, 73, 71, 69, 67, 65, 63])  # reaches 78 (today_hi)
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15),
                               trend=_trend(_t(78, 58), _t(85, 63), []))
    assert any(c["cat"] == "TREND" and c["verdict"] == "Cooler day" for c in cards)
```

Add a forward-pivot integration test and `_today_high_passed` unit tests:

```python
def test_build_cards_forward_pivot_when_high_passed():
    # remaining hours peak at 70°, below today's high (78°) -> pivot to tomorrow
    hrs = _hours([70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15),
                               trend=_trend(_t(78, 58), _t(85, 63), [], tomorrow=_t(84)))
    trend = [c for c in cards if c["cat"] == "TREND"]
    assert trend and "tomorrow" in trend[0]["detail"]


def test_today_high_passed_high_still_ahead():
    hrs = [{"hour": 9 + i, "temp_f": t}
           for i, t in enumerate([70, 74, 78, 84, 82, 80])]
    assert advice._today_high_passed(hrs, 84) is False   # reaches the high


def test_today_high_passed_high_behind():
    hrs = [{"hour": 9 + i, "temp_f": t}
           for i, t in enumerate([80, 78, 76, 74, 72, 70])]
    assert advice._today_high_passed(hrs, 84) is True     # 80 < 84 - 1


def test_today_high_passed_tolerance_boundary():
    hrs = [{"hour": 12, "temp_f": 83}]
    assert advice._today_high_passed(hrs, 84) is False    # within 1°F tolerance
    hrs = [{"hour": 12, "temp_f": 82}]
    assert advice._today_high_passed(hrs, 84) is True      # more than 1°F below


def test_today_high_passed_ignores_tomorrow_after_wrap():
    # window wraps past midnight: today's leading run is [22, 23]; tomorrow's warm
    # 90° must NOT count toward today reaching its high.
    hrs = [{"hour": 22, "temp_f": 70}, {"hour": 23, "temp_f": 68},
           {"hour": 0, "temp_f": 90}, {"hour": 1, "temp_f": 88}]
    assert advice._today_high_passed(hrs, 78) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_advice.py -k "high_passed or forward_pivot" -v`
Expected: FAIL — `advice._today_high_passed` does not exist yet.

- [ ] **Step 3: Add the constant, helper, and wire `build_cards`**

In `inky_weather/advice.py`, add the constant next to the other trend constants (after `TREND_WINDOW_MARGIN`):

```python
TREND_HIGH_REACHED_TOL = 1  # °F; remaining window still "reaches" the daily high
```

Add the helper (place it just above `_trend_card`):

```python
def _today_high_passed(hours, today_hi):
    """True once today's remaining forecast no longer reaches the daily high.

    The hourly feed is forward-only, so 'today's remaining hours' are its leading
    run — up to the first wrap past midnight. If that run's warmest hour falls
    more than TREND_HIGH_REACHED_TOL below the day's high, today's peak is behind
    us and the trend card should pivot to tomorrow.
    """
    if not hours:
        return False
    run = [hours[0]]
    for prev, h in zip(hours, hours[1:]):
        if h["hour"] > prev["hour"]:
            run.append(h)
        else:
            break
    return max(h["temp_f"] for h in run) < today_hi - TREND_HIGH_REACHED_TOL
```

Update the trend call in `build_cards` (currently lines 279-282):

```python
    if trend:
        t = _trend_card(trend["today"], trend["yesterday"], trend["stretch_his"])
        if t:
            scored.append(t)
```

to:

```python
    if trend:
        t = _trend_card(trend["today"], trend["yesterday"], trend["stretch_his"],
                        tomorrow=trend.get("tomorrow"),
                        forward=_today_high_passed(hours, trend["today"]["hi_f"]))
        if t:
            scored.append(t)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_advice.py -v`
Expected: PASS (full file, including the adjusted `test_build_cards_includes_trend`).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: pivot trend forward once today's high has passed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Data plumbing — `tomorrow` in trend_input, fixture, and smoke tests

**Files:**
- Modify: `inky_weather/history.py:47-68` (`trend_input`)
- Modify: `inky_weather/main.py:44-48` (fixture trend + comment)
- Test: `tests/test_history.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: `history.trend_input(days, history, date)`; `advice._today_high_passed`, `advice._trend_card` (Tasks 2–3); `weather.load_from_fixtures`.
- Produces: `trend_input(...)` return dict now includes `"tomorrow"`: `{"hi_f": int, "lo_f": int | None}` or `None`.

- [ ] **Step 1: Write failing tests**

In `tests/test_history.py`, extend the existing assembly test and add a no-tomorrow test:

```python
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
    assert ti["tomorrow"] == {"hi_f": 91, "lo_f": None}   # days[1] high; lo optional
    # 3 persisted past highs + 3 forecast forward highs, today excluded
    assert ti["stretch_his"] == [95, 93, 92, 91, 94, 90]


def test_trend_input_no_tomorrow_when_single_day():
    ti = history.trend_input([{"hi_f": 88, "lo_f": 60}], {}, datetime.date(2026, 7, 8))
    assert ti["tomorrow"] is None
```

In `tests/test_smoke.py`, replace `test_trend_absent_on_first_run` with a first-run forward-pivot test (the bundled fixture's 10am window never reaches its 84° daily high, so the proxy reports the high as passed and the card pivots forward — which needs no history):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_history.py tests/test_smoke.py -v`
Expected: FAIL — `trend_input` result has no `"tomorrow"` key (`KeyError`), and the new smoke test's `trend["tomorrow"]` lookup fails.

- [ ] **Step 3: Add `tomorrow` to `trend_input`**

In `inky_weather/history.py`, update `trend_input` (lines 47-68). Change the docstring return line and body to include `tomorrow`:

```python
def trend_input(days, history, date):
    """Assemble the trend card's inputs from Google `days` + persisted `history`.

    `days` is the Google daily forecast (index 0 = today). Returns a dict
    {"today", "yesterday", "tomorrow", "stretch_his"} or None when there is no
    forecast:
      - today:      {"hi_f","lo_f"} from the forecast (always present).
      - yesterday:  {"hi_f","lo_f"} recorded for date-1, or None (no history yet).
      - tomorrow:   {"hi_f","lo_f"} from days[1], or None (single-day forecast).
      - stretch_his: highs of the surrounding days (up to 3 persisted past days +
                     the next 3 forecast days), EXCLUDING today; used only for the
                     peak/dip upgrade.
    """
    if not days:
        return None
    today = {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]}
    tomorrow = ({"hi_f": days[1]["hi_f"], "lo_f": days[1].get("lo_f")}
                if len(days) >= 2 else None)
    yesterday = history.get((date - datetime.timedelta(days=1)).isoformat())
    past = []
    for back in (3, 2, 1):
        entry = history.get((date - datetime.timedelta(days=back)).isoformat())
        if entry:
            past.append(entry["hi_f"])
    forward = [d["hi_f"] for d in days[1:4]]
    return {"today": today, "yesterday": yesterday, "tomorrow": tomorrow,
            "stretch_his": past + forward}
```

- [ ] **Step 4: Add synthetic `tomorrow` to the fixture branch**

In `inky_weather/main.py`, update the fixture-branch trend (lines 44-48). Replace the comment and dict:

```python
        # No persisted history offline — synthesize a warmer "yesterday" so the
        # demo/preview shows a representative "Cooler day" trend card.
        trend = {"today": {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]},
                 "yesterday": {"hi_f": days[0]["hi_f"] + 6, "lo_f": days[0]["lo_f"] + 4},
                 "stretch_his": [d["hi_f"] for d in days[1:4]]}
```

with:

```python
        # No persisted history offline. Provide a synthetic yesterday and a real
        # tomorrow (days[1]) so the preview renders a trend card either way — the
        # bundled fixture's high is already behind its window, so it renders the
        # forward "tomorrow vs today" pivot.
        trend = {"today": {"hi_f": days[0]["hi_f"], "lo_f": days[0]["lo_f"]},
                 "yesterday": {"hi_f": days[0]["hi_f"] + 6, "lo_f": days[0]["lo_f"] + 4},
                 "tomorrow": {"hi_f": days[1]["hi_f"], "lo_f": days[1]["lo_f"]},
                 "stretch_his": [d["hi_f"] for d in days[1:4]]}
```

- [ ] **Step 5: Run the full suite to verify it passes**

Run: `python -m pytest -v`
Expected: PASS across all files. Confirm `test_fixture_synthesizes_cooler_day_trend` (a direct 3-arg `_trend_card` call, `forward=False`) still passes as a morning-branch contract, and the fixture render test still produces a non-error 800×480 image.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/history.py inky_weather/main.py tests/test_history.py tests/test_smoke.py
git commit -m "feat: thread tomorrow into trend_input and fixture preview

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Verify end-to-end render

**Files:** none (verification only)

- [ ] **Step 1: Render the fixture preview to a PNG**

Run: `python -m inky_weather.main --fixture --out /tmp/preview.out.png`
Expected: prints `Wrote /tmp/preview.out.png`.

- [ ] **Step 2: Inspect the image**

Open `/tmp/preview.out.png` and confirm:
- The precip strip shows two faint horizontal gridlines (50% + 100%) when the window has rain chance, with bars reading against them; on a dry window the strip is clean.
- The TREND card (if it wins a slot) reads `tomorrow NN° · N° warmer/cooler than today` (forward pivot, given the fixture's high is behind its window). No leftover `high NN° (±N)` format.

(`*.out.png` is gitignored — nothing to commit.)

---

## Self-Review

**Spec coverage:**
- Change 1 (precip gridlines, gated on rain chance, lines-only, faint gray) → Task 1. ✓
- Change 2a (detail names the days; low-append dropped) → Task 2. ✓
- Change 2b (forward pivot via `_today_high_passed` proxy, `TREND_HIGH_REACHED_TOL`) → Tasks 2 (branch) + 3 (proxy + wiring). ✓
- Stretch upgrade unchanged, new "this week" text → Task 2. ✓
- Data wiring (`trend_input` tomorrow, fixture tomorrow, `_trend_card` params, `build_cards` derives forward) → Tasks 2–4. ✓
- Testing (detail updates, pivot tests, `_today_high_passed` tests incl. wrap + tolerance, render gate test) → Tasks 1–4. ✓
- Out-of-scope items (no scoring/precedence change, OUTLOOK untouched, stretch stays today-anchored) respected. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `_trend_card(today, yesterday, stretch_his, tomorrow=None, forward=False)` used identically in Tasks 2–4; `_today_high_passed(hours, today_hi) -> bool` defined in Task 3 and called with `trend["today"]["hi_f"]`; `trend_input` returns the `"tomorrow"` key consumed via `trend.get("tomorrow")`. ✓
