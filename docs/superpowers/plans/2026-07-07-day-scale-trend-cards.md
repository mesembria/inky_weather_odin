# Day-scale Trend Cards Implementation Plan

> **⚠️ Superseded in part (2026-07-08).** This plan was executed as written, but a
> follow-up fix changed the backward trend's **data source** after live testing.
> The Open-Meteo `past_days` approach below (Task 1, and the `trend`/window pieces of
> Tasks 2/4/5) was replaced by **persisted Google daily highs** (`inky_weather/history.py`):
> the card now compares Google-today vs a locally-saved Google-yesterday, because raw
> Open-Meteo runs mean-biased vs the Google-anchored display and produced a card that
> contradicted the rest of the screen. `_trend_card`'s signature changed from
> `_trend_card(window)` to `_trend_card(today, yesterday, stretch_his)`, and the
> `trend` argument to `build_cards` is now a `{"today","yesterday","stretch_his"}`
> dict. `_outlook_card`, `_PRECEDENCE`, the intraday-swing removal, scores, and the
> banner layout are unchanged. See the revised **design spec** (`../specs/2026-07-07-day-scale-trend-cards-design.md`,
> "Data sourcing") for the shipped design. The task steps below are retained as the
> historical execution record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the intraday-swing TREND card with day-scale trend cards: an always-on day-over-day comparison (upgrading to a window peak/dip framing) plus an independent forward OUTLOOK card.

**Architecture:** A new single-source Open-Meteo daily call supplies a 7-day hi/lo window straddling today (`[t-3 … t+3]`, today at index 3). A pure `_trend_card(window)` renders the always-on backward card entirely from that Open-Meteo window (no cross-source delta bias). A pure `_outlook_card(days)` renders the forward card entirely from the existing Google 10-day forecast. Both feed the existing ranked `build_cards` selection.

**Tech Stack:** Python 3.13, `requests`, Pillow, pytest. Open-Meteo daily forecast API, Google Weather daily forecast API.

## Global Constraints

- The banner is exactly 3 card slots (`render.py:107`); slot 1 is always the DRESS card. Trend cards compete for the remaining 2 slots by score.
- A card is a dict `{"cat", "verdict", "detail", "accent"}`; accent ∈ `red|orange|blue|green|purple|ink|gray` (`advice.py:3-4`).
- Backward trend data is single-source Open-Meteo (delta must not mix sources). Forward OUTLOOK data is single-source Google.
- Graceful degradation: any optional fetch is wrapped in `main._safe(...)`; missing data means the dependent card is simply not emitted, never a crash.
- `TREND` score = 65; `OUTLOOK` score = 54 (informational). Real hazards (`_situational`) can still bump them.
- Fixtures contain only the JSON sections actually parsed (see existing `openmeteo_dewpoint.json` — `hourly` only).

---

## File Structure

- `inky_weather/weather.py` — **modify**: add `parse_trend_daily`, `trend_daily_url`, `fetch_trend_daily`, `load_trend_daily_fixture`.
- `inky_weather/fixtures/openmeteo_trenddaily.json` — **create**: 7-day Open-Meteo daily fixture.
- `inky_weather/advice.py` — **modify**: add threshold constants, `_trend_card`, `_outlook_card`; extend `_PRECEDENCE`; thread `days`/`trend` through `build_cards`; delete the intraday-swing block (lines 132-144).
- `inky_weather/main.py` — **modify**: stop discarding `days`, fetch/load the trend window, pass both to `build_cards`.
- `tests/test_weather.py` — **modify**: tests for `parse_trend_daily` + fixture loader.
- `tests/test_advice.py` — **modify**: unit tests for `_trend_card`, `_outlook_card`, and `build_cards` wiring.
- `tests/test_smoke.py` — **modify**: fixture-based TREND-present and degradation tests.

---

## Task 1: Open-Meteo trend-window data source

**Files:**
- Modify: `inky_weather/weather.py` (add functions after `load_dewpoint_fixture`, ~line 365)
- Create: `inky_weather/fixtures/openmeteo_trenddaily.json`
- Test: `tests/test_weather.py`

**Interfaces:**
- Consumes: module-level `_FORECAST_ENDPOINT` (`weather.py:275`), `requests`, `urlencode`, `json`, `os` (already imported).
- Produces:
  - `weather.parse_trend_daily(data) -> list[dict]` — each `{"hi_f": int, "lo_f": int}`, chronological. With `past_days=3&forecast_days=4` the list is `[t-3, t-2, t-1, today, t+1, t+2, t+3]`, today at index 3.
  - `weather.trend_daily_url(lat, long) -> str`
  - `weather.fetch_trend_daily(lat, long, timeout=20) -> list[dict]`
  - `weather.load_trend_daily_fixture(fixture_dir) -> list[dict]`

- [ ] **Step 1: Create the fixture file**

Create `inky_weather/fixtures/openmeteo_trenddaily.json` (daily-only, like the other trimmed Open-Meteo fixtures). Today (index 3) is 7° cooler than yesterday, low 5° lower, and not an extreme of the window:

```json
{
  "daily": {
    "time": ["2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"],
    "temperature_2m_max": [82, 84, 85, 78, 80, 83, 85],
    "temperature_2m_min": [60, 62, 63, 58, 59, 61, 62]
  }
}
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_weather.py` (it already defines `FIXTURE_DIR` and `_load_fixture`):

```python
def test_parse_trend_daily_returns_seven():
    data = _load_fixture("openmeteo_trenddaily.json")
    window = weather.parse_trend_daily(data)
    assert len(window) == 7
    assert window[3] == {"hi_f": 78, "lo_f": 58}   # today at index 3


def test_parse_trend_daily_rounds_and_skips_short():
    data = {"daily": {"time": ["2026-07-06", "2026-07-07"],
                      "temperature_2m_max": [84.6, 78.2],
                      "temperature_2m_min": [62.4]}}
    window = weather.parse_trend_daily(data)
    assert window == [{"hi_f": 85, "lo_f": 62}]     # min length across arrays, rounded


def test_parse_trend_daily_empty_on_missing_daily():
    assert weather.parse_trend_daily({}) == []


def test_trend_daily_url_has_past_and_forecast_days():
    url = weather.trend_daily_url(37.2, -80.4)
    assert "past_days=3" in url and "forecast_days=4" in url
    assert "temperature_2m_max" in url


def test_load_trend_daily_fixture():
    window = weather.load_trend_daily_fixture(FIXTURE_DIR)
    assert len(window) == 7 and window[2]["hi_f"] == 85
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_weather.py -k trend -v`
Expected: FAIL with `AttributeError: module 'inky_weather.weather' has no attribute 'parse_trend_daily'`

- [ ] **Step 4: Implement the functions**

Append to `inky_weather/weather.py` (after `load_dewpoint_fixture`):

```python
def parse_trend_daily(data):
    """Daily hi/lo window from an Open-Meteo daily response.

    Returns a list of {"hi_f": int, "lo_f": int}, chronological. With
    past_days=3 & forecast_days=4 that is [t-3, t-2, t-1, today, t+1, t+2, t+3]
    with today at index 3. Truncates to the shortest of the parallel arrays.
    """
    daily = data.get("daily", {})
    times = daily.get("time", [])
    his = daily.get("temperature_2m_max", [])
    los = daily.get("temperature_2m_min", [])
    n = min(len(times), len(his), len(los))
    return [{"hi_f": round(his[i]), "lo_f": round(los[i])} for i in range(n)]


def trend_daily_url(lat, long):
    params = {"latitude": lat, "longitude": long,
              "daily": "temperature_2m_max,temperature_2m_min",
              "temperature_unit": "fahrenheit", "timezone": "auto",
              "past_days": 3, "forecast_days": 4}
    return "{}?{}".format(_FORECAST_ENDPOINT, urlencode(params))


def fetch_trend_daily(lat, long, timeout=20):
    resp = requests.get(trend_daily_url(lat, long), timeout=timeout)
    resp.raise_for_status()
    return parse_trend_daily(resp.json())


def load_trend_daily_fixture(fixture_dir):
    with open(os.path.join(fixture_dir, "openmeteo_trenddaily.json")) as f:
        return parse_trend_daily(json.load(f))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_weather.py -k trend -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add inky_weather/weather.py inky_weather/fixtures/openmeteo_trenddaily.json tests/test_weather.py
git commit -m "feat: Open-Meteo trend-window daily fetch (past+forward hi/lo)"
```

---

## Task 2: Backward always-on TREND card

**Files:**
- Modify: `inky_weather/advice.py` (add constants near line 10; add `_trend_card` after `_w1`, ~line 71)
- Test: `tests/test_advice.py`

**Interfaces:**
- Consumes: `weather.parse_trend_daily` output — a 7-element list of `{"hi_f": int, "lo_f": int}`, today at index 3.
- Produces: `advice._trend_card(window) -> (int, card) | None`. Always returns a card when `len(window) == 7`; returns `None` otherwise. `card["cat"] == "TREND"`, score is the module constant `TREND_SCORE`.

- [ ] **Step 1: Add threshold constants**

After `MUGGY_DEWPOINT_F = 60` (`advice.py:10`) add:

```python
TREND_HI_FLAT = 2        # |Δhigh| <= this reads as "Steady"
TREND_HI_BIG = 10        # |Δhigh| >= this reads as "Much warmer/cooler"
TREND_LOW_DETAIL = 5     # append the low delta when |Δlow| >= this
TREND_WINDOW_MARGIN = 3  # today must beat its nearest neighbor by this to be a peak/dip
TREND_SCORE = 65
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_advice.py`. Helper builds a 7-day window from highs (+ optional lows):

```python
def _window(highs, lows=None):
    lows = lows or [h - 20 for h in highs]
    return [{"hi_f": h, "lo_f": l} for h, l in zip(highs, lows)]


def test_trend_card_cooler_day():
    # today (idx 3) 7 cooler than yesterday, not a window extreme
    s, c = advice._trend_card(_window([82, 84, 85, 78, 80, 83, 85]))
    assert s == advice.TREND_SCORE and c["cat"] == "TREND"
    assert c["verdict"] == "Cooler day" and c["accent"] == "blue"
    assert c["detail"] == "high 78° (-7)"


def test_trend_card_appends_low_when_it_moves():
    s, c = advice._trend_card(_window([82, 84, 85, 78, 80, 83, 85],
                                      [60, 62, 63, 58, 59, 61, 62]))
    assert c["detail"] == "high 78° (-7) · low 58° (-5)"


def test_trend_card_steady_when_flat():
    s, c = advice._trend_card(_window([80, 81, 79, 80, 81, 80, 79]))
    assert c["verdict"] == "Steady" and c["accent"] == "gray"
    assert c["detail"] == "high 80° · ~ yesterday"


def test_trend_card_much_warmer():
    s, c = advice._trend_card(_window([60, 62, 64, 76, 74, 72, 70]))
    assert c["verdict"] == "Much warmer" and c["accent"] == "orange"
    assert c["detail"] == "high 76° (+12)"


def test_trend_card_coolest_stretch_upgrade():
    # today strictly the lowest high, beats nearest neighbor by >= 3
    s, c = advice._trend_card(_window([84, 85, 86, 70, 80, 83, 85]))
    assert c["verdict"] == "Coolest stretch" and c["accent"] == "blue"
    assert c["detail"] == "high 70° · warmer around it"


def test_trend_card_warmest_stretch_upgrade():
    s, c = advice._trend_card(_window([70, 72, 74, 90, 76, 73, 71]))
    assert c["verdict"] == "Warmest stretch" and c["accent"] == "orange"
    assert c["detail"] == "high 90° · cooler around it"


def test_trend_card_none_without_full_window():
    assert advice._trend_card([]) is None
    assert advice._trend_card(_window([80, 81, 82])) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_advice.py -k trend_card -v`
Expected: FAIL with `AttributeError: module 'inky_weather.advice' has no attribute '_trend_card'`

- [ ] **Step 4: Implement `_trend_card`**

Add after `_w1` (`advice.py:71`):

```python
def _trend_card(window):
    """Always-on day-over-day TREND card, upgrading to a window peak/dip framing.

    `window` is the 7-day hi/lo list from weather.parse_trend_daily
    ([t-3..t+3], today at index 3). Single-source (Open-Meteo) so the
    day-over-day delta carries no cross-model bias. Returns (score, card) or
    None when the window is not a full 7 days.
    """
    if not window or len(window) != 7:
        return None
    today, yest = window[3], window[2]
    his = [d["hi_f"] for d in window]
    others = his[:3] + his[4:]
    # window upgrade: today a strict peak/dip beating its nearest neighbor by margin
    if today["hi_f"] < min(others) and min(others) - today["hi_f"] >= TREND_WINDOW_MARGIN:
        return (TREND_SCORE, _card("TREND", "Coolest stretch",
                                   "high {}° · warmer around it".format(today["hi_f"]), "blue"))
    if today["hi_f"] > max(others) and today["hi_f"] - max(others) >= TREND_WINDOW_MARGIN:
        return (TREND_SCORE, _card("TREND", "Warmest stretch",
                                   "high {}° · cooler around it".format(today["hi_f"]), "orange"))
    # default: day-over-day on the high
    dhi = today["hi_f"] - yest["hi_f"]
    dlo = today["lo_f"] - yest["lo_f"]
    if dhi <= -TREND_HI_BIG:
        verdict, accent = "Much cooler", "blue"
    elif dhi <= -(TREND_HI_FLAT + 1):
        verdict, accent = "Cooler day", "blue"
    elif dhi >= TREND_HI_BIG:
        verdict, accent = "Much warmer", "orange"
    elif dhi >= TREND_HI_FLAT + 1:
        verdict, accent = "Warmer day", "orange"
    else:
        verdict, accent = "Steady", "gray"
    if verdict == "Steady":
        detail = "high {}° · ~ yesterday".format(today["hi_f"])
    else:
        detail = "high {}° ({:+d})".format(today["hi_f"], dhi)
        if abs(dlo) >= TREND_LOW_DETAIL:
            detail += " · low {}° ({:+d})".format(today["lo_f"], dlo)
    return (TREND_SCORE, _card("TREND", verdict, detail, accent))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_advice.py -k trend_card -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: always-on day-over-day TREND card with window peak/dip upgrade"
```

---

## Task 3: Forward OUTLOOK card

**Files:**
- Modify: `inky_weather/advice.py` (add constants near the Task 2 constants; add `_outlook_card` after `_trend_card`)
- Test: `tests/test_advice.py`

**Interfaces:**
- Consumes: the Google daily forecast list from `weather.parse_daily` — dicts with keys `hi_f` (int) and `name` (3-letter weekday str); index 0 = today.
- Produces: `advice._outlook_card(days) -> (int, card) | None`. `card["cat"] == "OUTLOOK"`, score `OUTLOOK_SCORE`.

- [ ] **Step 1: Add threshold constants**

Below the Task 2 constants in `advice.py`:

```python
OUTLOOK_NET = 8          # min |net high change| over the next 3 days to fire
OUTLOOK_SCORE = 54       # informational; below TREND
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_advice.py`:

```python
def _days(highs, names=None):
    names = names or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [{"hi_f": h, "name": n} for h, n in zip(highs, names)]


def test_outlook_warming_trend():
    s, c = advice._outlook_card(_days([70, 74, 78, 82]))
    assert s == advice.OUTLOOK_SCORE and c["cat"] == "OUTLOOK"
    assert c["verdict"] == "Warming trend" and c["accent"] == "orange"
    assert c["detail"] == "→ 82° by Thu"


def test_outlook_cooling_trend():
    s, c = advice._outlook_card(_days([82, 78, 74, 70]))
    assert c["verdict"] == "Cooling trend" and c["accent"] == "blue"
    assert c["detail"] == "→ 70° by Thu"


def test_outlook_none_when_change_below_threshold():
    assert advice._outlook_card(_days([70, 72, 71, 74])) is None   # net +4 < 8


def test_outlook_none_when_reversal_dominates():
    # net +8 but a -6 reversal in the middle: not a consistent direction
    assert advice._outlook_card(_days([70, 84, 78, 78])) is None


def test_outlook_none_without_enough_days():
    assert advice._outlook_card(_days([70, 74, 80])) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_advice.py -k outlook -v`
Expected: FAIL with `AttributeError: module 'inky_weather.advice' has no attribute '_outlook_card'`

- [ ] **Step 4: Implement `_outlook_card`**

Add after `_trend_card` in `advice.py`:

```python
def _outlook_card(days):
    """Forward OUTLOOK card: direction of the next few forecast days.

    `days` is the Google daily forecast (index 0 = today). Fires when the net
    high change over the next 3 days is at least OUTLOOK_NET and dominates any
    opposite-direction reversal (net magnitude >= twice the largest reversal).
    Returns (score, card) or None.
    """
    if not days or len(days) < 4:
        return None
    his = [days[i]["hi_f"] for i in range(4)]        # today + next 3
    steps = [his[i + 1] - his[i] for i in range(3)]
    net = his[3] - his[0]
    if abs(net) < OUTLOOK_NET:
        return None
    reversal = max([0] + [(-s if net > 0 else s) for s in steps])
    if abs(net) < 2 * reversal:
        return None
    end = days[3]
    if net > 0:
        return (OUTLOOK_SCORE, _card("OUTLOOK", "Warming trend",
                                     "→ {}° by {}".format(end["hi_f"], end["name"]), "orange"))
    return (OUTLOOK_SCORE, _card("OUTLOOK", "Cooling trend",
                                 "→ {}° by {}".format(end["hi_f"], end["name"]), "blue"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_advice.py -k outlook -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: forward OUTLOOK card for multi-day warming/cooling trend"
```

---

## Task 4: Wire trend cards into build_cards; remove intraday card

**Files:**
- Modify: `inky_weather/advice.py` (`_PRECEDENCE` line 74-75; `build_cards` line 203-213; delete intraday block lines 132-144)
- Test: `tests/test_advice.py`

**Interfaces:**
- Consumes: `_trend_card`, `_outlook_card` (Tasks 2-3).
- Produces: `advice.build_cards(hours, bands, gust, aqi, sun, date, days=None, trend=None) -> list[card]`. New trailing keyword params `days` (Google forecast list) and `trend` (Open-Meteo window). Existing 6-positional-arg calls keep working (both default `None`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_advice.py` (reuses `_window`, `_days`, and the existing `_hours`):

```python
def test_build_cards_includes_trend():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15),
                               trend=_window([82, 84, 85, 78, 80, 83, 85]))
    assert any(c["cat"] == "TREND" and c["verdict"] == "Cooler day" for c in cards)


def test_build_cards_hazard_can_bump_trend():
    # multiple hazards (storm + gusty wind) fill both non-DRESS slots ahead of TREND
    hrs = _hours([78] * 12, thunder=65, pop=90)   # STORMS=90, OUTDOORS(rain)=72
    cards = advice.build_cards(hrs, [], [40] * 12, [], {}, datetime.date(2026, 7, 15),
                               trend=_window([82, 84, 85, 78, 80, 83, 85]))
    assert any(c["cat"] == "STORMS" for c in cards)
    assert not any(c["cat"] == "TREND" for c in cards)


def test_build_cards_trend_absent_without_data():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"},
                               datetime.date(2026, 7, 15), trend=[])
    assert not any(c["cat"] == "TREND" for c in cards)


def test_build_cards_includes_outlook():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {}, datetime.date(2026, 7, 15),
                               days=_days([70, 74, 78, 82]))
    assert any(c["cat"] == "OUTLOOK" for c in cards)
```

Note: `gust` is the 3rd positional arg of `build_cards`, so `test_build_cards_hazard_can_bump_trend` passes `[40]*12` in that slot (not as a keyword, which would collide). The hazards are STORMS=90, WIND-gusty=80, and OUTDOORS-rain=72 — all beat TREND=65, filling both non-DRESS slots.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_advice.py -k "build_cards_includes or build_cards_hazard_can or build_cards_trend_absent" -v`
Expected: FAIL — `test_build_cards_includes_trend` fails because `build_cards()` got an unexpected keyword argument `trend`.

- [ ] **Step 3: Delete the intraday-swing block**

Remove these lines from `_situational` (`advice.py:132-144`):

```python
    T = [h["temp_f"] for h in hours]
    half = T[len(T) // 2:]
    base = len(T) // 2
    lo_late, hi_late = min(half), max(half)
    cool_sw, warm_sw = T[0] - lo_late, hi_late - T[0]
    if warm_sw >= 18 and warm_sw >= cool_sw:
        j = base + half.index(hi_late)
        C.append((58, _card("TREND", "Warming up",
                            "{}°→{}° by {}".format(T[0], hi_late, hours[j]["ampm_label"].lower()), "orange")))
    elif cool_sw >= 18:
        j = base + half.index(lo_late)
        C.append((58, _card("TREND", "Cooling off",
                            "{}°→{}° by {}".format(T[0], lo_late, hours[j]["ampm_label"].lower()), "blue")))
```

- [ ] **Step 4: Add OUTLOOK to precedence**

Change `_PRECEDENCE` (`advice.py:74-75`) to insert `"OUTLOOK"` right after `"TREND"`:

```python
_PRECEDENCE = ["ICE", "SNOW", "STORMS", "SMOKE", "WIND", "OUTDOORS", "SUN",
               "TREND", "OUTLOOK", "OVERNIGHT", "SPREAD", "MOON", "DAYLIGHT"]
```

- [ ] **Step 5: Update `build_cards`**

Replace `build_cards` (`advice.py:203-213`) with:

```python
def build_cards(hours, bands, gust, aqi, sun, date, days=None, trend=None):
    sun = sun or {}
    gmax = max(gust) if gust else 0
    amax = max(aqi) if aqi else 0
    cards = [temp_card(hours)]
    scored = _situational(hours, gmax, amax)
    has_hazard = any(s >= 50 for s, _ in scored)
    scored += _info_tier(hours, bands, sun, date, has_hazard)
    if trend:
        t = _trend_card(trend)
        if t:
            scored.append(t)
    if days:
        o = _outlook_card(days)
        if o:
            scored.append(o)
    scored.sort(key=_tiebreak_key)
    cards += [c for _, c in scored[:2]]
    return cards
```

- [ ] **Step 6: Run the full advice suite to verify it passes**

Run: `pytest tests/test_advice.py -v`
Expected: PASS (all — new build_cards tests plus the pre-existing ones unchanged).

- [ ] **Step 7: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: wire TREND/OUTLOOK into build_cards; drop intraday swing card"
```

---

## Task 5: Orchestrate in main.py + fixture end-to-end

**Files:**
- Modify: `inky_weather/main.py` (`build_image` lines 35-64)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `weather.load_trend_daily_fixture`, `weather.fetch_trend_daily` (Task 1); `advice.build_cards(..., days=, trend=)` (Task 4).
- Produces: no new public interface; `build_image` now passes `days` and `trend` to `build_cards`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_smoke.py`:

```python
def test_fixture_trend_card_present():
    import datetime
    from inky_weather import weather, advice, main
    hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    trend = weather.load_trend_daily_fixture(main.FIXTURE_DIR)
    cards = advice.build_cards(hours, [], [], [], {}, datetime.date(2026, 7, 7),
                               days=days, trend=trend)
    assert any(c["cat"] == "TREND" for c in cards)


def test_fixture_trend_absent_on_missing_data():
    import datetime
    from inky_weather import weather, advice, main
    hours, days = weather.load_from_fixtures(main.FIXTURE_DIR)
    cards = advice.build_cards(hours, [], [], [], {}, datetime.date(2026, 7, 7),
                               days=days, trend=[])
    assert not any(c["cat"] == "TREND" for c in cards)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_smoke.py -k trend -v`
Expected: FAIL — `test_fixture_trend_card_present` fails: no TREND card, because `build_image`/fixtures don't yet load the window (and `load_trend_daily_fixture` isn't called by anything under test). Specifically the assertion `any(... "TREND" ...)` fails.

Note: this test calls `build_cards` directly, so it fails only until Task 1's `load_trend_daily_fixture` exists and returns the 7-day window. If Task 1 is complete it should already pass the *loader*; the assertion still exercises the wiring contract. Proceed to wire `main.py` so the real render path uses it too.

- [ ] **Step 3: Wire `build_image`**

In `inky_weather/main.py`, update `build_image` (lines 35-64). Stop discarding `days`, load/fetch the trend window, and pass both to `build_cards`.

Change the fixture branch (line 37) from `hours, _days = ...` to:

```python
        hours, days = weather.load_from_fixtures(FIXTURE_DIR)
        fh = hours[0]["hour"]
        bands, gust = weather.load_ensemble_fixture(FIXTURE_DIR, fh)
        aqi = weather.load_airquality_fixture(FIXTURE_DIR, fh)
        dew = weather.load_dewpoint_fixture(FIXTURE_DIR, fh)
        trend = weather.load_trend_daily_fixture(FIXTURE_DIR)
        sun = {"sunset": "8p", "sunrise": "6a"}
```

Change the live branch (line 44) from `hours, _days = ...` to:

```python
        hours, days = weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])
        fh = hours[0]["hour"]
        bands_gust = _safe(lambda: weather.fetch_ensemble(cfg["lat"], cfg["long"], fh),
                           default=([], []))
        bands, gust = bands_gust
        aqi = _safe(lambda: weather.fetch_air_quality(cfg["lat"], cfg["long"], fh), default=[])
        sun = _safe(lambda: weather.fetch_sun(cfg["lat"], cfg["long"]), default={})
        dew = _safe(lambda: weather.fetch_dewpoint(cfg["lat"], cfg["long"], fh), default=[])
        trend = _safe(lambda: weather.fetch_trend_daily(cfg["lat"], cfg["long"]), default=[])
```

Change the `build_cards` call (line 64) to:

```python
    cards = advice.build_cards(hours, bands, gust, aqi, sun, now.date(), days=days, trend=trend)
```

- [ ] **Step 4: Run the smoke suite to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS — including the existing `test_fixture_render_end_to_end` (render still 800x480, non-error) and the two new trend tests.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS (all tests across the project).

- [ ] **Step 6: Commit**

```bash
git add inky_weather/main.py tests/test_smoke.py
git commit -m "feat: orchestrate trend-window fetch and pass trend/days into build_cards"
```

---

## Self-Review

**Spec coverage:**
- Day-over-day always-on incl. "Steady" → Task 2 (`_trend_card`, Steady branch). ✓
- High headline, low as detail when it moved → Task 2 (`TREND_LOW_DETAIL`). ✓
- Window peak/dip upgrade, either/or with day-over-day → Task 2 (upgrade branches return before day-over-day). ✓
- Forward OUTLOOK independent → Task 3 + Task 4 (appended independently). ✓
- Open-Meteo `past_days` single-source backward; Google forward → Task 1 (`past_days=3&forecast_days=4`, all one source) + Task 3 (Google `days`). ✓
- Score ≈ 65 backward, ~54 forward; hazards can bump → Task 2/3 constants, Task 4 wiring + `test_build_cards_hazard_can_bump_trend`. ✓
- Graceful degradation → Task 5 `_safe(..., default=[])`; `_trend_card`/`build_cards` guard on falsy/short data (`test_build_cards_trend_absent_without_data`). ✓
- Delete intraday-swing card → Task 4 Step 3. ✓
- `_PRECEDENCE` updated → Task 4 Step 4. ✓
- Fixture + degradation e2e tests → Task 1 fixture, Task 5 tests. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `parse_trend_daily` returns `{"hi_f","lo_f"}` dicts (Task 1) — consumed by `_trend_card` via `d["hi_f"]/d["lo_f"]` (Task 2). Google `days` dicts use `hi_f`/`name` — consumed by `_outlook_card` (Task 3), matching `parse_daily`'s documented keys (`weather.py:6-7`). `build_cards` new kwargs `days`/`trend` defined in Task 4, passed in Task 5. Scores are module constants referenced by name in tests. ✓
