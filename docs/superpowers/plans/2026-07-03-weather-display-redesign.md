# Weather Display Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the weather.com-style hourly/daily render with a predictive decision-support display: a 3-card advice banner over a full-width ensemble temperature graph.

**Architecture:** Keep Google Weather as the deterministic source (temp, pop, thunder, uv, icons). Add Open-Meteo (ensemble temperature members → spread band + confidence; wind gusts; sunrise/sunset) and Open-Meteo Air-Quality (US AQI). A new pure `advice.py` turns those numbers into ≤3 ranked cards. `render.py` is rewritten to draw the new layout with a bundled Oswald font. All network sources degrade gracefully — a partial/failed fetch must never crash the display.

**Tech Stack:** Python 3, Pillow, requests, pytest. No new dependencies. Rendering with Pillow primitives; fonts bundled under `inky_weather/assets/fonts/`.

## Global Constraints

- **Canvas:** 800×480 RGB, quantized to the Inky Impression's ~7 fixed colors (black, white, red, green, blue, yellow, orange). Flat fills only.
- **Palette (render.py):** `BLACK/INK=(20,22,28)`, `WHITE=(255,255,255)`, `RED=(200,30,30)`, `BLUE=(30,70,200)`, `GREEN=(30,140,60)`, `ORANGE=(235,120,0)`, `PURPLE=(150,40,140)`, `GRAY=(120,122,130)`.
- **Accent names (advice ↔ render boundary):** advice emits an accent as a **string** (`"red"|"orange"|"blue"|"green"|"purple"|"ink"`); render maps names→RGB. Advice never imports render.
- **Font:** bundled **Oswald** (OFL) variable TTF at `inky_weather/assets/fonts/Oswald.ttf`; weight 600 for labels/verdicts/numerals, weight 300 for detail text.
- **Units:** request Open-Meteo in `temperature_unit=fahrenheit`, `wind_speed_unit=mph`, `timezone=auto`.
- **Graceful degradation:** every Open-Meteo fetch is wrapped so failure returns `None`; the display renders with whatever succeeded (no band, no gust/aqi/sun cards) rather than crashing.
- **Non-commercial:** Open-Meteo free tier (no API key) — personal display, allowed.
- **Card dict shape:** `{"cat": str, "verdict": str, "detail": str, "accent": str}`.
- **Existing Google hour dict keys** (from `weather.parse_hourly`, unchanged): `hour, ampm_label, is_daytime, condition, icon_uri, temp_f, feels_f, pop, precip_type, thunder, uv`.
- Run tests with: `python3 -m pytest -q` (repo uses `pytest.ini` with `-p no:debugging`).
- Commit after every task. Branch is `inky-impression-port` (already checked out); commit there.

---

## File Structure

- `inky_weather/assets/fonts/Oswald.ttf` — **create** (bundled display font).
- `inky_weather/weather.py` — **modify**: add ensemble + air-quality + extras fetch/parse and a percentile helper.
- `inky_weather/advice.py` — **create**: pure advice logic (cards + confidence + moon).
- `inky_weather/render.py` — **rewrite**: new layout (header/badge, banner, ensemble graph).
- `inky_weather/main.py` — **modify**: orchestrate the extra fetches; pass through to render.
- `inky_weather/fixtures/openmeteo_ensemble.json`, `openmeteo_airquality.json` — **create**.
- `tests/test_advice.py` — **create**.
- `tests/test_weather.py`, `tests/test_render.py`, `tests/test_smoke.py` — **modify**.

---

## Task 1: Bundle Oswald font + display-font loader

**Files:**
- Create: `inky_weather/assets/fonts/Oswald.ttf`
- Modify: `inky_weather/render.py` (font loader + palette)
- Test: `tests/test_render.py`

**Interfaces:**
- Produces: `render.display_font(size, weight=600) -> ImageFont`; `render.ACCENTS: dict[str, tuple]`; palette constants `INK, WHITE, RED, BLUE, GREEN, ORANGE, PURPLE, GRAY`.

- [ ] **Step 1: Add the font asset**

Run:
```bash
mkdir -p inky_weather/assets/fonts
curl -sL -o inky_weather/assets/fonts/Oswald.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf"
python3 -c "from PIL import ImageFont; f=ImageFont.truetype('inky_weather/assets/fonts/Oswald.ttf',30); print('ok', f.getname())"
```
Expected: prints `ok ('Oswald', ...)`.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_render.py`:
```python
def test_display_font_loads_and_varies_weight():
    f = render.display_font(30, 600)
    assert hasattr(f, "getbbox")
    assert render.ACCENTS["red"] == render.RED
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render.py::test_display_font_loads_and_varies_weight -q`
Expected: FAIL (`AttributeError: module 'inky_weather.render' has no attribute 'display_font'`).

- [ ] **Step 4: Add palette + loader to `render.py` (purely additive)**

This task only **adds** to `render.py` — do not remove or change existing constants/functions yet (the old panel code is deleted in Task 9). Add `import os` to the imports, and add this block after the existing color constants (existing `RED/BLUE/GREEN/ORANGE/WHITE/BLACK/PAPER` are reused as-is):
```python
import os  # add to the existing imports at the top

# --- new redesign palette + font (additive) ---
INK = (20, 22, 28)
PURPLE = (150, 40, 140)
GRAY = (120, 122, 130)
FAINT = (225, 226, 230)

ACCENTS = {"red": RED, "orange": ORANGE, "blue": BLUE, "green": GREEN,
           "purple": PURPLE, "ink": INK, "gray": GRAY}

_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "Oswald.ttf")


def display_font(size, weight=600):
    """Bundled Oswald at the given size and weight (300 or 600)."""
    f = ImageFont.truetype(_FONT_PATH, int(size))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_render.py::test_display_font_loads_and_varies_weight -q`
Expected: PASS. Old render tests still pass too (this task is additive), but the full suite goes red between Tasks 4–9 while `advice`/`render` are mid-migration — run only the targeted tests each task until Task 12.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/assets/fonts/Oswald.ttf inky_weather/render.py tests/test_render.py
git commit -m "feat: bundle Oswald font + display-font loader and palette"
```

---

## Task 2: Ensemble temperature bands + wind gusts (Open-Meteo)

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

**Interfaces:**
- Produces:
  - `weather.percentile(sorted_vals, p) -> float`
  - `weather.parse_ensemble(data, first_hour, count=12) -> (bands, gust)` where `bands` is a list of `(p10, p25, p75, p90)` int tuples and `gust` is a list of int mph, each length ≤ `count`, aligned so element 0 is the ensemble hour whose local hour == `first_hour`.
  - `weather.fetch_ensemble(lat, long, first_hour, count=12, timeout=20) -> (bands, gust)`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:
```python
def test_percentile_interpolates():
    assert weather.percentile([10, 20, 30, 40], 50) == 25


def test_parse_ensemble_aligns_and_summarizes():
    data = {"hourly": {
        "time": ["2026-07-03T12:00", "2026-07-03T13:00", "2026-07-03T14:00"],
        "temperature_2m": [70, 72, 74],
        "temperature_2m_member01": [68, 70, 72],
        "temperature_2m_member02": [74, 76, 78],
        "wind_gusts_10m": [10, 12, 14],
        "wind_gusts_10m_member01": [12, 14, 16],
    }}
    bands, gust = weather.parse_ensemble(data, first_hour=13, count=2)
    assert len(bands) == 2
    p10, p25, p75, p90 = bands[0]      # aligned to the 13:00 row
    assert p10 <= p25 <= p75 <= p90
    assert gust[0] == 13               # mean of [12, 14]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py::test_parse_ensemble_aligns_and_summarizes -q`
Expected: FAIL (`AttributeError: ... 'parse_ensemble'`).

- [ ] **Step 3: Implement in `weather.py`**

Add:
```python
_ENSEMBLE_ENDPOINT = "https://ensemble-api.open-meteo.com/v1/ensemble"


def percentile(sorted_vals, p):
    """Linear-interpolated percentile (p in 0..100) of a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _align_index(times, first_hour):
    """Index of the first entry whose local hour == first_hour (else 0)."""
    for i, t in enumerate(times):
        if int(t[11:13]) == first_hour:
            return i
    return 0


def parse_ensemble(data, first_hour, count=12):
    """Return (bands, gust): per-hour temp (p10,p25,p75,p90) and mean gust mph."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return [], []
    start = _align_index(times, first_hour)
    temp_keys = [k for k in hourly if k.startswith("temperature_2m")]
    gust_keys = [k for k in hourly if k.startswith("wind_gusts_10m")]
    bands, gust = [], []
    for i in range(start, min(start + count, len(times))):
        temps = sorted(hourly[k][i] for k in temp_keys
                       if i < len(hourly[k]) and hourly[k][i] is not None)
        bands.append((round(percentile(temps, 10)), round(percentile(temps, 25)),
                      round(percentile(temps, 75)), round(percentile(temps, 90))))
        gs = [hourly[k][i] for k in gust_keys
              if i < len(hourly[k]) and hourly[k][i] is not None]
        gust.append(round(sum(gs) / len(gs)) if gs else 0)
    return bands, gust


def ensemble_url(lat, long, count=12):
    params = {"latitude": lat, "longitude": long, "models": "gfs_seamless",
              "hourly": "temperature_2m,wind_gusts_10m",
              "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
              "timezone": "auto", "forecast_days": 2}
    return "{}?{}".format(_ENSEMBLE_ENDPOINT, urlencode(params))


def fetch_ensemble(lat, long, first_hour, count=12, timeout=20):
    resp = requests.get(ensemble_url(lat, long, count), timeout=timeout)
    resp.raise_for_status()
    return parse_ensemble(resp.json(), first_hour, count)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -q -k "percentile or parse_ensemble"`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: Open-Meteo ensemble temp bands + wind gusts"
```

---

## Task 3: Air-quality + sun times (Open-Meteo)

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

**Interfaces:**
- Produces:
  - `weather.parse_air_quality(data, first_hour, count=12) -> list[int]` (US AQI per hour, aligned like Task 2)
  - `weather.fetch_air_quality(lat, long, first_hour, count=12, timeout=20) -> list[int]`
  - `weather.parse_sun(data) -> dict` with keys `sunrise` and `sunset` as compact labels (e.g. `"6a"`, `"8p"`) or `None`
  - `weather.fetch_sun(lat, long, timeout=20) -> dict`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:
```python
def test_parse_air_quality_aligns():
    data = {"hourly": {"time": ["2026-07-03T12:00", "2026-07-03T13:00"],
                        "us_aqi": [40, 55]}}
    assert weather.parse_air_quality(data, first_hour=13, count=2) == [55]


def test_parse_sun_labels():
    data = {"daily": {"sunrise": ["2026-07-03T06:12"], "sunset": ["2026-07-03T20:31"]}}
    s = weather.parse_sun(data)
    assert s["sunrise"] == "6a" and s["sunset"] == "8p"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -q -k "air_quality or parse_sun"`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Implement in `weather.py`**

Add:
```python
_AIRQUALITY_ENDPOINT = "https://air-quality-api.open-meteo.com/v1/air-quality"
_FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def parse_air_quality(data, first_hour, count=12):
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    aqi = hourly.get("us_aqi", [])
    if not times:
        return []
    start = _align_index(times, first_hour)
    out = []
    for i in range(start, min(start + count, len(times))):
        v = aqi[i] if i < len(aqi) and aqi[i] is not None else 0
        out.append(int(v))
    return out


def air_quality_url(lat, long):
    params = {"latitude": lat, "longitude": long, "hourly": "us_aqi",
              "timezone": "auto", "forecast_days": 2}
    return "{}?{}".format(_AIRQUALITY_ENDPOINT, urlencode(params))


def fetch_air_quality(lat, long, first_hour, count=12, timeout=20):
    resp = requests.get(air_quality_url(lat, long), timeout=timeout)
    resp.raise_for_status()
    return parse_air_quality(resp.json(), first_hour, count)


def _sun_label(iso):
    hour = int(iso[11:13])
    suffix = "a" if hour < 12 else "p"
    h12 = hour % 12 or 12
    return "{}{}".format(h12, suffix)


def parse_sun(data):
    daily = data.get("daily", {})
    rise = daily.get("sunrise") or []
    setl = daily.get("sunset") or []
    return {"sunrise": _sun_label(rise[0]) if rise else None,
            "sunset": _sun_label(setl[0]) if setl else None}


def sun_url(lat, long):
    params = {"latitude": lat, "longitude": long, "daily": "sunrise,sunset",
              "timezone": "auto", "forecast_days": 1}
    return "{}?{}".format(_FORECAST_ENDPOINT, urlencode(params))


def fetch_sun(lat, long, timeout=20):
    resp = requests.get(sun_url(lat, long), timeout=timeout)
    resp.raise_for_status()
    return parse_sun(resp.json())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -q -k "air_quality or parse_sun"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: Open-Meteo air-quality (US AQI) + sunrise/sunset parsing"
```

---

## Task 4: advice.py — card shape, temperature card, moon, confidence

**Files:**
- Create: `inky_weather/advice.py`
- Test: `tests/test_advice.py` (create)

**Interfaces:**
- Produces:
  - `advice.temp_card(hours) -> dict` (slot-1 card)
  - `advice.moon_illumination(date) -> float` (0..1)
  - `advice.confidence(bands) -> (label, accent)` where accent is `"green"|"orange"|"red"`
  - helper `advice._card(cat, verdict, detail, accent) -> dict`

- [ ] **Step 1: Write the failing test**

Create `tests/test_advice.py`:
```python
import datetime
from inky_weather import advice


def _hours(temps, feels=None, day=True, pop=0, ptype="RAIN", thunder=0, uv=3):
    feels = feels or temps
    out = []
    for i, (t, f) in enumerate(zip(temps, feels)):
        h = (9 + i) % 24
        out.append({"hour": h, "ampm_label": "{}{}".format(h % 12 or 12,
                    "a" if h < 12 else "p"), "is_daytime": day, "condition": "CLEAR",
                    "icon_uri": "", "temp_f": t, "feels_f": f, "pop": pop,
                    "precip_type": ptype, "thunder": thunder, "uv": uv})
    return out


def test_temp_card_cold_band_fills_30s_40s():
    c = advice.temp_card(_hours([40, 42, 44, 45, 44, 42, 40, 38, 37, 36, 35, 34]))
    assert c["verdict"] == "Cold"
    assert c["cat"] == "DRESS"


def test_temp_card_warm_muggy():
    c = advice.temp_card(_hours([80, 82, 83, 84, 83, 82, 81, 80, 79, 78, 77, 76],
                                feels=[86, 88, 89, 90, 89, 88, 87, 86, 85, 84, 83, 82]))
    assert c["verdict"] == "Warm & muggy"


def test_moon_full_is_high():
    # 2026-07-28 is ~full
    assert advice.moon_illumination(datetime.date(2026, 7, 28)) > 0.9


def test_confidence_tight_band_is_high():
    bands = [(70, 71, 73, 74)] * 12
    label, accent = advice.confidence(bands)
    assert label == "HIGH CONFIDENCE" and accent == "green"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_advice.py -q`
Expected: FAIL (`ModuleNotFoundError: inky_weather.advice`).

- [ ] **Step 3: Implement `inky_weather/advice.py`**

```python
"""Pure advice logic: turn parsed forecast numbers into <=3 ranked cards.

A card is a dict {"cat", "verdict", "detail", "accent"} where accent is one of
"red"|"orange"|"blue"|"green"|"purple"|"ink" (render maps names to RGB).
"""
import datetime
import math

ICE_TYPES = ("ICE", "SLEET", "FREEZING_RAIN")


def _card(cat, verdict, detail, accent):
    return {"cat": cat, "verdict": verdict, "detail": detail, "accent": accent}


def moon_illumination(date):
    """Illuminated fraction of the moon (0=new, 1=full) for a date."""
    ref = datetime.date(2000, 1, 6)          # a known new moon
    days = (date - ref).days + 0.5
    phase = (days % 29.53058867) / 29.53058867
    return (1 - math.cos(2 * math.pi * phase)) / 2


def confidence(bands):
    """(label, accent) from the mean p10-p90 width of the ensemble band."""
    if not bands:
        return ("NO ENSEMBLE", "gray")
    avg = sum(p90 - p10 for p10, _, _, p90 in bands) / len(bands)
    if avg < 6:
        return ("HIGH CONFIDENCE", "green")
    if avg < 10:
        return ("MIXED CONFIDENCE", "orange")
    return ("LOW AGREEMENT", "red")


def temp_card(hours):
    """Slot-1 'what to wear' card: a plain state line keyed on the day's high."""
    T = [h["temp_f"] for h in hours]
    FL = [h["feels_f"] for h in hours]
    hi, lo = max(T), min(T)
    uvmax = max(h["uv"] for h in hours)
    muggy = any(f > t + 2 for f, t in zip(FL, T))
    wet = any(h["pop"] >= 50 for h in hours)
    frost = " · frost AM" if lo <= 32 else ""
    if hi >= 100:
        return _card("DRESS", "Dangerous heat", "{}-{}° · hydrate, shade".format(lo, hi), "red")
    if hi >= 90:
        return _card("DRESS", "Hot", "{}-{}° · UV {}, shade".format(lo, hi, uvmax), "red")
    if hi >= 80:
        return _card("DRESS", "Warm & muggy" if muggy else "Warm",
                     "{}-{}° · {}".format(lo, hi, "humid" if muggy else "pleasant"), "orange")
    if hi >= 62:
        return _card("DRESS", "Mild", "{}-{}° · easy layers".format(lo, hi), "green")
    if hi >= 48:
        return _card("DRESS", "Cool & damp" if wet else "Cool",
                     "{}-{}° · layers".format(lo, hi), "blue")
    if hi >= 33:
        return _card("DRESS", "Cold", "{}-{}° · coat{}".format(lo, hi, frost), "blue")
    return _card("DRESS", "Frigid", "{}-{}° · bundle up".format(lo, hi), "blue")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_advice.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: advice temp card, moon phase, confidence badge"
```

---

## Task 5: advice.py — daytime situational cards + OVERNIGHT

**Files:**
- Modify: `inky_weather/advice.py`
- Test: `tests/test_advice.py`

**Interfaces:**
- Produces `advice._situational(hours, gust, aqi) -> list[(score, card)]` covering ICE/SNOW/STORMS/SMOKE/WIND/RAIN/UV/TREND (daytime-framed) and the single OVERNIGHT card. `gust` is an int (max mph) and `aqi` an int (max) — callers pass the window maxima.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_advice.py`:
```python
def test_daytime_storm_scores_high():
    hrs = _hours([78]*12, thunder=65, pop=90)
    cards = dict((s, c["verdict"]) for s, c in advice._situational(hrs, 5, 20))
    assert any(v.startswith("T-storms") for v in cards.values())


def test_overnight_storm_uses_windows_shut():
    hrs = _hours([64]*12, day=False, thunder=40, pop=80)
    cards = [c for _, c in advice._situational(hrs, 5, 20) if c["cat"] == "OVERNIGHT"]
    assert cards and cards[0]["verdict"] == "Storms overnight"


def test_rain_card_is_daytime_timing():
    hrs = _hours([60]*12, pop=70)
    rain = [c for _, c in advice._situational(hrs, 5, 20) if c["cat"] == "OUTDOORS"]
    assert rain and rain[0]["verdict"].startswith("Rain ")
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_advice.py -q -k "situational or overnight or rain_card"`
Expected: FAIL (`AttributeError: _situational`).

- [ ] **Step 3: Implement `_situational` in `advice.py`**

```python
def _w0(hs):
    return hs[0]["ampm_label"].lower()


def _w1(hs):
    return hs[-1]["ampm_label"].lower()


def _situational(hours, gust, aqi):
    """Daytime-framed hazard cards + one OVERNIGHT roll-up. Returns [(score, card)]."""
    C = []
    day_h = [h for h in hours if h["is_daytime"]]
    night_h = [h for h in hours if not h["is_daytime"]]
    ice_day = [h for h in day_h if h["precip_type"] in ICE_TYPES and h["pop"] >= 30]
    snow_day = [h for h in day_h if h["precip_type"] == "SNOW" and h["pop"] >= 30]
    wet_day = [h for h in day_h if h["pop"] >= 50
               and h["precip_type"] not in ICE_TYPES + ("SNOW",)]
    uvmax = max((h["uv"] for h in day_h), default=0)
    dstorm = max(day_h, key=lambda h: h["thunder"]) if day_h else None
    dthun = dstorm["thunder"] if dstorm else 0

    if ice_day:
        C.append((97, _card("ICE", "Ice {}-{}".format(_w0(ice_day), _w1(ice_day)),
                            "Icy roads · avoid driving", "purple")))
    if snow_day:
        C.append((95, _card("SNOW", "Snow {}".format("all day" if len(snow_day) >= 8 else _w0(snow_day)),
                            "{}\" likely · roads slick".format(6 if len(snow_day) >= 8 else 3), "purple")))
    if dthun >= 45:
        C.append((90, _card("STORMS", "T-storms {}".format(dstorm["ampm_label"].lower()),
                            "{}% · brief, heavy".format(dthun), "red")))
    elif dthun >= 25:
        C.append((68, _card("STORMS", "Stray storm {}".format(dstorm["ampm_label"].lower()),
                            "{}% · mainly dry".format(dthun), "orange")))
    if aqi >= 150:
        C.append((88, _card("SMOKE", "Unhealthy air", "AQI {} · stay indoors".format(aqi), "purple")))
    elif aqi >= 100:
        C.append((64, _card("SMOKE", "Hazy air", "AQI {} · limit exertion".format(aqi), "orange")))
    if gust >= 35:
        C.append((80, _card("WIND", "Gusty", "Gusts {} mph · secure loose items".format(gust), "orange")))
    elif gust >= 25:
        C.append((56, _card("WIND", "Breezy", "Gusts {} mph".format(gust), "blue")))
    if wet_day:
        C.append((72, _card("OUTDOORS", "Rain {}-{}".format(_w0(wet_day), _w1(wet_day)),
                            "{}% · umbrella".format(max(h["pop"] for h in wet_day)), "blue")))
    if day_h and uvmax >= 9:
        C.append((60, _card("SUN", "Extreme UV", "Index {} · cover up".format(uvmax), "red")))
    elif day_h and uvmax >= 6:
        C.append((44, _card("SUN", "Strong UV", "Index {} midday · hat+SPF".format(uvmax), "orange")))

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

    if night_h:
        nlo = min(h["temp_f"] for h in night_h)
        nstorm = max(h["thunder"] for h in night_h)
        nwet = any(h["pop"] >= 50 and h["precip_type"] not in ICE_TYPES + ("SNOW",) for h in night_h)
        nsnow = any(h["precip_type"] == "SNOW" and h["pop"] >= 30 for h in night_h)
        nice = any(h["precip_type"] in ICE_TYPES and h["pop"] >= 30 for h in night_h)
        if nice and not ice_day:
            card, sc = _card("OVERNIGHT", "Ice overnight", "Low {}° · icy roads AM".format(nlo), "purple"), 88
        elif nstorm >= 30 and dthun < 25:
            card, sc = _card("OVERNIGHT", "Storms overnight", "Low {}° · windows shut".format(nlo), "red"), 85
        elif nsnow and not snow_day:
            card, sc = _card("OVERNIGHT", "Snow overnight", "Low {}° · roads slick AM".format(nlo), "purple"), 82
        elif nwet and not wet_day:
            card, sc = _card("OVERNIGHT", "Rain overnight", "Low {}° · windows shut".format(nlo), "blue"), 60
        elif nlo <= 45:
            card, sc = _card("OVERNIGHT", "Cold night", "Low {}° · heat on".format(nlo), "blue"), 55
        elif nlo >= 70:
            card, sc = _card("OVERNIGHT", "Warm night", "Low {}° · stuffy, fan on".format(nlo), "orange"), 50
        elif nlo <= 68:
            card, sc = _card("OVERNIGHT", "Windows open", "Low {}° · comfortable".format(nlo), "green"), 50
        else:
            card, sc = _card("OVERNIGHT", "Mild night", "Low {}°".format(nlo), "green"), 50
        C.append((sc, card))
    return C
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_advice.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: advice daytime situational cards + overnight roll-up"
```

---

## Task 6: advice.py — info tier + final selection (`build_cards`)

**Files:**
- Modify: `inky_weather/advice.py`
- Test: `tests/test_advice.py`

**Interfaces:**
- Produces `advice.build_cards(hours, bands, gust, aqi, sun, date) -> list[dict]`:
  - `hours`: Google hour dicts. `bands`: list of `(p10,p25,p75,p90)` (may be `[]`).
  - `gust`: list of int mph (may be `[]`). `aqi`: list of int (may be `[]`). `sun`: dict `{sunrise, sunset}` (may be `{}`). `date`: `datetime.date`.
  - Returns 2 or 3 cards, first is always the temp card, rest by score desc with fixed tie-break precedence.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_advice.py`:
```python
import datetime


def test_build_cards_calm_day_fills_info_tier():
    hrs = _hours([60, 63, 66, 68, 70, 71, 71, 70, 68, 66, 64, 62])
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"}, datetime.date(2026, 7, 15))
    assert cards[0]["cat"] == "DRESS"
    cats = [c["cat"] for c in cards]
    assert "DAYLIGHT" in cats or "OUTDOORS" in cats   # info tier filled a slot


def test_build_cards_full_moon_night():
    hrs = _hours([60, 58, 56, 55, 54, 53, 52, 52, 53, 54, 55, 56], day=False)
    cards = advice.build_cards(hrs, [], [], [], {}, datetime.date(2026, 7, 28))
    assert any(c["cat"] == "MOON" for c in cards)


def test_build_cards_hazards_beat_info_tier():
    hrs = _hours([78]*12, thunder=65, pop=90)
    cards = advice.build_cards(hrs, [], [], [], {"sunset": "8p"}, datetime.date(2026, 7, 15))
    assert cards[0]["cat"] == "DRESS"
    assert any(c["cat"] == "STORMS" for c in cards)
    assert not any(c["cat"] in ("MOON", "DAYLIGHT") for c in cards)  # crowded out
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_advice.py -q -k build_cards`
Expected: FAIL (`AttributeError: build_cards`).

- [ ] **Step 3: Implement `build_cards` (and `_info_tier`) in `advice.py`**

```python
# tie-break precedence for equal scores: lower index = wins
_PRECEDENCE = ["ICE", "SNOW", "STORMS", "SMOKE", "WIND", "OUTDOORS", "SUN",
               "TREND", "OVERNIGHT", "SPREAD", "MOON", "DAYLIGHT"]


def _tiebreak_key(scored):
    score, card = scored
    try:
        rank = _PRECEDENCE.index(card["cat"])
    except ValueError:
        rank = len(_PRECEDENCE)
    return (-score, rank)


def _band_width(bands):
    return max((p90 - p10 for p10, _, _, p90 in bands), default=0)


def _info_tier(hours, bands, sun, date, has_hazard):
    C = []
    day_h = [h for h in hours if h["is_daytime"]]
    night_h = [h for h in hours if not h["is_daytime"]]
    daymost = len(day_h) >= len(night_h)
    # SWING
    if bands:
        widths = [(p90 - p10, i) for i, (p10, _, _, p90) in enumerate(bands)]
        wmax, wi = max(widths)
        if wmax >= 15:
            p10, _, _, p90 = bands[wi]
            C.append((40, _card("SPREAD", "Could be {}-{}°".format(int(p10), int(p90)),
                                "models split by {}".format(hours[wi]["ampm_label"].lower()), "purple")))
    # MOON
    if night_h:
        il = moon_illumination(date)
        if il >= 0.90:
            C.append((36, _card("MOON", "Full moon" if il >= 0.985 else "Nearly full moon",
                                "{}% lit · bright night".format(int(round(il * 100))), "orange")))
    # calm nudge
    if not has_hazard:
        C.append((34, _card("OUTDOORS", "Get outside", "Clear & calm ahead", "green") if daymost
                  else _card("OVERNIGHT", "Quiet night", "Clear & calm", "green")))
    # DAYLIGHT
    if daymost and sun.get("sunset"):
        C.append((32, _card("DAYLIGHT", "Sunset {}".format(sun["sunset"]), "plan outdoor time", "orange")))
    elif not daymost and sun.get("sunrise"):
        C.append((32, _card("DAYLIGHT", "Sunrise {}".format(sun["sunrise"]), "first light", "orange")))
    return C


def build_cards(hours, bands, gust, aqi, sun, date):
    sun = sun or {}
    gmax = max(gust) if gust else 0
    amax = max(aqi) if aqi else 0
    cards = [temp_card(hours)]
    scored = _situational(hours, gmax, amax)
    has_hazard = any(s >= 50 for s, _ in scored)
    scored += _info_tier(hours, bands, sun, date, has_hazard)
    scored.sort(key=_tiebreak_key)
    cards += [c for _, c in scored[:2]]
    return cards
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_advice.py -q`
Expected: PASS (all advice tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/advice.py tests/test_advice.py
git commit -m "feat: advice info tier (swing/moon/daylight) + ranked selection"
```

---

## Task 7: render.py — header band, confidence badge, advice banner

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces:
  - `render.draw_header(draw, location, date_str, updated_str, badge)` where `badge=(label, accent_name)`
  - `render.draw_banner(draw, cards)` — draws 2–3 cards across the banner
  - Layout constants: `BANNER_Y=50`, `BANNER_H=104`, `HEADER_RULE_Y=40`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:
```python
def test_draw_banner_marks_pixels():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
    d = ImageDraw.Draw(img)
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "63-81°", "accent": "orange"},
             {"cat": "STORMS", "verdict": "T-storms 2p", "detail": "65%", "accent": "red"}]
    render.draw_banner(d, cards)
    assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_render.py::test_draw_banner_marks_pixels -q`
Expected: FAIL (`AttributeError: draw_banner`).

- [ ] **Step 3: Implement in `render.py`** (this **replaces** the existing `draw_header` — the old 4-arg version is dead once the new one is defined; add the rest new)

```python
BANNER_Y = 50
BANNER_H = 104
HEADER_RULE_Y = 40


def _ctext(d, t, cx, cy, font, fill, anchor="mm"):
    d.text((cx, cy), t, font=font, fill=fill, anchor=anchor)


def draw_header(draw, location, date_str, updated_str, badge):
    _ctext(draw, (location or "").upper(), 20, 20, display_font(26, 600), INK, anchor="lm")
    w = draw.textlength((location or "").upper(), font=display_font(26, 600))
    _ctext(draw, date_str, 28 + w, 22, display_font(14, 300), GRAY, anchor="lm")
    if badge:
        label, accent = badge
        _ctext(draw, "◈ " + label, WIDTH - 20, 15, display_font(11, 600),
               ACCENTS.get(accent, GRAY), anchor="rm")
    _ctext(draw, updated_str + " · NEXT 12H", WIDTH - 20, 30, display_font(11, 300), GRAY, anchor="rm")
    draw.line([20, HEADER_RULE_Y, WIDTH - 20, HEADER_RULE_Y], fill=INK, width=2)


def _draw_card(draw, x, y, w, h, card):
    accent = ACCENTS.get(card["accent"], INK)
    _ctext(draw, card["cat"], x + 14, y + 15, display_font(13, 600), accent, anchor="lm")
    vf = display_font(30 if len(card["verdict"]) <= 15 else 26, 600)
    _ctext(draw, card["verdict"], x + 14, y + 45, vf, INK, anchor="lm")
    _ctext(draw, card["detail"], x + 14, y + h - 13, display_font(13, 300), GRAY, anchor="lm")


def draw_banner(draw, cards):
    cw = (WIDTH - 40) / 3
    for i, card in enumerate(cards):
        x = 20 + i * cw
        _draw_card(draw, x, BANNER_Y, cw, BANNER_H, card)
        if i > 0:
            draw.line([x, BANNER_Y + 8, x, BANNER_Y + BANNER_H - 8], fill=FAINT, width=1)
    draw.line([20, BANNER_Y + BANNER_H, WIDTH - 20, BANNER_Y + BANNER_H], fill=INK, width=1)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_render.py::test_draw_banner_marks_pixels -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: render header band, confidence badge, advice banner"
```

---

## Task 8: render.py — ensemble graph

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces `render.draw_graph(img, draw, hours, bands, icons, gx, gy, gw, gh)`:
  - `hours`: Google hour dicts. `bands`: list of `(p10,p25,p75,p90)` (may be `[]` → no band drawn).
  - `icons`: list of RGBA images parallel to hours (may contain `None`).
  - Draws: nested band (if present), temp gridlines + °F labels, the deterministic temp line with per-hour °F labels, per-hour condition icons, and a bottom precip strip (grounded pop% bars, colored by kind, with % labels).
- Layout: `GRAPH_Y = BANNER_Y + BANNER_H + 2`, `GRAPH_H = HEIGHT - GRAPH_Y - 8`, precip band `82px`.
- Consumes: `weather.precip_kind(pop, precip_type, thunder)` (existing) for bar color.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:
```python
def test_draw_graph_runs_with_and_without_band():
    from PIL import Image, ImageDraw
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 20 * (i % 3), "precip_type": "RAIN", "thunder": 0, "uv": 3}
             for i in range(12)]
    bands = [(t - 3, t - 1, t + 1, t + 3) for t in (h["temp_f"] for h in hours)]
    for b in (bands, []):
        img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
        d = ImageDraw.Draw(img)
        render.draw_graph(img, d, hours, b, [None] * 12, 14, 160, render.WIDTH - 28, 300)
        assert img.tobytes() != Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE).tobytes()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_render.py::test_draw_graph_runs_with_and_without_band -q`
Expected: FAIL (`AttributeError: draw_graph`).

- [ ] **Step 3: Implement in `render.py`** (`weather` is already imported at the top of the module; **replace** the existing `temp_color` body with the finer thresholds below)

```python
GRAPH_Y = BANNER_Y + BANNER_H + 2
GRAPH_H = HEIGHT - GRAPH_Y - 8
BAND_OUT = (213, 220, 240)
BAND_IN = (178, 190, 224)

_KIND_BAR = {"storm": RED, "snow": PURPLE, "mix": PURPLE, "rain": BLUE, "dry": BLUE}


def temp_color(temp_f):   # replaces the existing 2-stop version
    if temp_f >= 80:
        return RED
    if temp_f >= 72:
        return ORANGE
    if temp_f >= 55:
        return INK
    return BLUE


def draw_graph(img, draw, hours, bands, icons, gx, gy, gw, gh):
    n = len(hours)
    temps = [h["temp_f"] for h in hours]
    has_band = len(bands) == n and n > 0
    lows = [b[0] for b in bands] if has_band else temps
    highs = [b[3] for b in bands] if has_band else temps
    mn, mx = min(lows), max(highs)
    rng = (mx - mn) or 1
    bandh = 82
    axis_y = gy + gh - 16
    top = gy + 40
    plot_h = (axis_y - bandh) - top
    lx = gx + 30
    xs = [lx + (gw - 32) * (i + 0.5) / n for i in range(n)]

    def Y(t):
        return top + plot_h * (1 - (t - mn) / rng)

    # temp gridlines + labels
    lo10 = int((mn // 10) * 10)
    hi10 = int((mx // 10 + 1) * 10)
    step = 10 if (hi10 - lo10) >= 20 else 5
    for g in range(lo10, hi10 + 1, step):
        if g < mn - 2 or g > mx + 2:
            continue
        gyv = Y(g)
        draw.line([lx, gyv, gx + gw, gyv], fill=(230, 231, 236), width=1)
        _ctext(draw, "{}°".format(g), gx + 2, gyv, display_font(11, 600), (165, 168, 178), anchor="lm")

    # nested ensemble band
    if has_band:
        def poly(los, his):
            return list(zip(xs, [Y(v) for v in his])) + list(zip(reversed(xs), [Y(v) for v in reversed(los)]))
        draw.polygon(poly([b[0] for b in bands], [b[3] for b in bands]), fill=BAND_OUT)
        draw.polygon(poly([b[1] for b in bands], [b[2] for b in bands]), fill=BAND_IN)

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
    _ctext(draw, "RAIN %", gx + 2, pbase - bandh + 2, display_font(9, 600), GRAY, anchor="lm")

    # temp line + points + labels + icons
    ys = [Y(t) for t in temps]
    draw.line(list(zip(xs, ys)), fill=INK, width=3, joint="curve")
    for i, h in enumerate(hours):
        x, y = xs[i], ys[i]
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=INK)
        _ctext(draw, "{}°".format(h["temp_f"]), x, y - 14, display_font(19, 600), temp_color(h["temp_f"]))
        if icons[i] is not None:
            img.paste(icons[i], (int(x - 14), int(top - 32)), icons[i])

    # x axis
    draw.line([lx, axis_y, gx + gw, axis_y], fill=(200, 200, 205), width=1)
    for i, h in enumerate(hours):
        _ctext(draw, h["ampm_label"], xs[i], axis_y + 8, display_font(12, 300), GRAY)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_render.py::test_draw_graph_runs_with_and_without_band -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: render ensemble graph (band, gridlines, temp line, precip)"
```

---

## Task 9: render.py — compose render_display + render_error

**Files:**
- Modify: `inky_weather/render.py` (replace old `LAYOUT`/`render_display`/`draw_hourly_panel`/`draw_daily_strip` machinery)
- Test: `tests/test_render.py` (replace stale layout tests)

**Interfaces:**
- Produces `render.render_display(hours, bands, hour_icons, cards, badge, location_name, date_str, updated_str) -> Image` (800×480 RGB).
- Keeps `render.render_error(message) -> Image` (update to use `display_font`).
- `ICON_SZ_HOUR = 28` (used by main for icon sizing).

- [ ] **Step 1: Delete obsolete code**

In `render.py`, remove the now-unused old machinery: the `LAYOUT` dict, `draw_hourly_panel`, `_draw_precip_bar`, `draw_daily_row`, `draw_daily_strip`, `kind_color`, `draw_bolt`, `load_font`, `_FONT_CANDIDATES`, `draw_centered_text`, `ICON_SZ_DAY`, and the old `render_display`. Keep: palette + `display_font` + `ACCENTS` (Task 1), `draw_header`/`draw_banner`/`_ctext`/`_draw_card` (Task 7), `draw_graph`/`temp_color`/`_KIND_BAR` (Task 8). Change `ICON_SZ_HOUR = 34` → `ICON_SZ_HOUR = 28`.

- [ ] **Step 2: Replace stale tests**

In `tests/test_render.py`, delete the tests that target removed functions: `test_layout_zones_sum_to_height`, `test_kind_color_known_kinds`, `test_load_font_returns_font`, and `test_draw_centered_text_runs`. (`test_dimensions` and `test_temp_color_hot_is_red_ish` stay — they still pass.) Add:
```python
def test_render_display_dimensions_with_and_without_band():
    hours = [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12), "is_daytime": True,
              "condition": "CLEAR", "icon_uri": "", "temp_f": 70 + i, "feels_f": 70 + i,
              "pop": 10, "precip_type": "RAIN", "thunder": 0, "uv": 3} for i in range(12)]
    bands = [(t - 3, t - 1, t + 1, t + 3) for t in (h["temp_f"] for h in hours)]
    cards = [{"cat": "DRESS", "verdict": "Warm", "detail": "70-81°", "accent": "orange"}]
    for b in (bands, []):
        img = render.render_display(hours, b, [None] * 12, cards,
                                    ("HIGH CONFIDENCE", "green"), "Town", "Thu Jul 3", "2p")
        assert img.size == (800, 480)
```

- [ ] **Step 3: Implement compose**

```python
def render_display(hours, bands, hour_icons, cards, badge,
                   location_name, date_str, updated_str):
    """Compose the full 800x480 image. Returns an RGB PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw_graph(img, draw, hours, bands, hour_icons, 14, GRAPH_Y, WIDTH - 28, GRAPH_H)
    draw_banner(draw, cards)
    draw_header(draw, location_name, date_str, updated_str, badge)
    return img


def render_error(message):
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, 30], fill=RED)
    draw.text((10, 7), "Weather update failed", font=display_font(15, 600), fill=WHITE)
    _ctext(draw, message, WIDTH / 2, HEIGHT / 2, display_font(18, 600), INK)
    _ctext(draw, "Will retry next hour", WIDTH / 2, HEIGHT / 2 + 34, display_font(13, 300), GRAY)
    return img
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_render.py -q`
Expected: PASS (all render tests, including the new compose test).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: rewrite render_display for new layout; drop weather.com panels"
```

---

## Task 10: main.py — orchestrate sources with graceful degradation

**Files:**
- Modify: `inky_weather/main.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: `weather.fetch_live`, `weather.fetch_ensemble`, `weather.fetch_air_quality`, `weather.fetch_sun`, `advice.build_cards`, `advice.confidence`, `render.render_display`, `render.ICON_SZ_HOUR`, `icons.get_icon`.
- Produces: updated `build_image(use_fixture, cfg) -> Image` that gathers all sources (each Open-Meteo call wrapped so failure → empty/`None`) and renders.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_smoke.py`:
```python
def test_optional_fetch_swallows_errors():
    from inky_weather import main
    assert main._safe(lambda: (_ for _ in ()).throw(RuntimeError("boom")), default="X") == "X"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_smoke.py::test_optional_fetch_swallows_errors -q`
Expected: FAIL (`AttributeError: _safe`).

- [ ] **Step 3: Rewrite the gather/build part of `main.py`**

Replace `_gather`, `_icons_for`, and `build_image` with:
```python
from . import weather, icons, render, advice


def _safe(fn, default=None):
    """Run fn, returning default on any exception (graceful degradation)."""
    try:
        return fn()
    except Exception:
        return default


def _icons_for(items, size):
    return [icons.get_icon(item["icon_uri"], size, ICON_CACHE) for item in items]


def build_image(use_fixture, cfg):
    if use_fixture:
        hours, _days = weather.load_from_fixtures(FIXTURE_DIR)
        bands, gust = weather.load_ensemble_fixture(FIXTURE_DIR, hours[0]["hour"])
        aqi = weather.load_airquality_fixture(FIXTURE_DIR, hours[0]["hour"])
        sun = {"sunset": "8p", "sunrise": "6a"}
    else:
        hours, _days = weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])
        fh = hours[0]["hour"]
        bands_gust = _safe(lambda: weather.fetch_ensemble(cfg["lat"], cfg["long"], fh),
                           default=([], []))
        bands, gust = bands_gust
        aqi = _safe(lambda: weather.fetch_air_quality(cfg["lat"], cfg["long"], fh), default=[])
        sun = _safe(lambda: weather.fetch_sun(cfg["lat"], cfg["long"]), default={})

    hour_icons = _icons_for(hours, render.ICON_SZ_HOUR)
    now = datetime.datetime.now()
    cards = advice.build_cards(hours, bands, gust, aqi, sun, now.date())
    badge = advice.confidence(bands)
    return render.render_display(
        hours, bands, hour_icons, cards, badge,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M%p").lower().lstrip("0"),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_smoke.py::test_optional_fetch_swallows_errors -q`
Expected: PASS. (The `--fixture` path needs Task 11's fixtures + loaders; full smoke run happens there.)

- [ ] **Step 5: Commit**

```bash
git add inky_weather/main.py tests/test_smoke.py
git commit -m "feat: main orchestrates ensemble/aqi/sun with graceful degradation"
```

---

## Task 11: Fixtures + offline end-to-end render

**Files:**
- Create: `inky_weather/fixtures/openmeteo_ensemble.json`, `inky_weather/fixtures/openmeteo_airquality.json`
- Modify: `inky_weather/weather.py` (fixture loaders), `tests/test_smoke.py`

**Interfaces:**
- Produces:
  - `weather.load_ensemble_fixture(fixture_dir, first_hour) -> (bands, gust)`
  - `weather.load_airquality_fixture(fixture_dir, first_hour) -> list[int]`

- [ ] **Step 1: Generate fixtures aligned to the Google hourly fixture**

Run (creates ensemble + air-quality JSON whose `time` array covers the Google fixture's first hour, with 31 members spread ±spread):
```bash
python3 - <<'PY'
import json, os, random
fx = "inky_weather/fixtures"
hourly = json.load(open(os.path.join(fx, "hourly_response.json")))
rows = hourly["forecastHours"]
def iso(o):
    d = o["displayDateTime"]
    return "{:04d}-{:02d}-{:02d}T{:02d}:00".format(d["year"], d["month"], d["day"], d["hours"])
times = [iso(o) for o in rows]
temps_f = [round(o["temperature"]["degrees"] * 9 / 5 + 32) for o in rows]
random.seed(1)
ens = {"hourly": {"time": times, "temperature_2m": temps_f}}
for m in range(1, 32):
    ens["hourly"]["temperature_2m_member{:02d}".format(m)] = [
        round(t + random.uniform(-1, 1) - (i * 0.3) + random.uniform(-i * 0.4, i * 0.4))
        for i, t in enumerate(temps_f)]
ens["hourly"]["wind_gusts_10m"] = [8 + i % 5 for i in range(len(times))]
json.dump(ens, open(os.path.join(fx, "openmeteo_ensemble.json"), "w"))
aq = {"hourly": {"time": times, "us_aqi": [40 + (i % 3) * 5 for i in range(len(times))]}}
json.dump(aq, open(os.path.join(fx, "openmeteo_airquality.json"), "w"))
print("wrote fixtures for", len(times), "hours; first hour", rows[0]["displayDateTime"]["hours"])
PY
```
Expected: prints the count and first hour.

- [ ] **Step 2: Write the failing smoke test**

Add to `tests/test_smoke.py`:
```python
def test_fixture_render_end_to_end(tmp_path):
    from inky_weather import main
    out = tmp_path / "out.png"
    main.main(["--fixture", "--out", str(out)])
    from PIL import Image
    assert Image.open(out).size == (800, 480)
```

- [ ] **Step 3: Run to verify fail**

Run: `python3 -m pytest tests/test_smoke.py::test_fixture_render_end_to_end -q`
Expected: FAIL (`AttributeError: load_ensemble_fixture`).

- [ ] **Step 4: Implement fixture loaders in `weather.py`**

```python
def load_ensemble_fixture(fixture_dir, first_hour, count=12):
    with open(os.path.join(fixture_dir, "openmeteo_ensemble.json")) as f:
        return parse_ensemble(json.load(f), first_hour, count)


def load_airquality_fixture(fixture_dir, first_hour, count=12):
    with open(os.path.join(fixture_dir, "openmeteo_airquality.json")) as f:
        return parse_air_quality(json.load(f), first_hour, count)
```

- [ ] **Step 5: Run to verify pass + eyeball the render**

Run:
```bash
python3 -m pytest tests/test_smoke.py -q
python3 -m inky_weather.main --fixture --out /tmp/redesign_check.png && open /tmp/redesign_check.png
```
Expected: tests PASS; the PNG shows the header+badge, a 3-card banner, and the ensemble graph with a real band.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/fixtures/openmeteo_ensemble.json inky_weather/fixtures/openmeteo_airquality.json inky_weather/weather.py tests/test_smoke.py
git commit -m "feat: Open-Meteo fixtures + offline end-to-end render"
```

---

## Task 12: Full suite + README refresh

**Files:**
- Modify: `README.md`
- Test: whole suite

- [ ] **Step 1: Run the whole suite**

Run: `python3 -m pytest -q`
Expected: all PASS. If any old `test_render`/`test_icons` reference removed symbols, delete those stale assertions (they test deleted functions).

- [ ] **Step 2: Update README**

In `README.md`, update the intro/description to reflect the new design (advice banner + ensemble graph; Open-Meteo as a second source; icons still from Google) and note that Open-Meteo needs no key. Keep the setup/cron sections.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: describe redesigned advice + ensemble display"
```

---

## Self-Review Notes (implementer: read before starting)

- **Alignment assumption:** Open-Meteo (`timezone=auto`) local hours are matched to the Google first hour by hour-of-day (`_align_index`). If a location's Open-Meteo timezone disagrees with Google's local hour, the band may be off by the offset — acceptable for v1; revisit with explicit `start_hour`/`end_hour` if observed on the Pi.
- **Precip ensemble spread (spec §6) is intentionally simplified for v1:** the strip shows the deterministic Google pop% as grounded, kind-colored bars with % labels (the must-keep readable number). The temperature band is the real ensemble showpiece. Member-based precip spread (floating box-plot / p90 cap) is a follow-up once the deterministic strip is confirmed legible on the panel (spec open item #2 + #4).
- **Thresholds** live as literals in `advice.py` for v1 (validated over 7 scenarios in the spec). Moving them into `config.py` overrides is a later refinement (spec §5) and is not required for a working display.
- **Icon dithering** check (spec §9) is the manual `--fixture --out` eyeball in Task 11 Step 5 plus an on-panel check when deploying.
