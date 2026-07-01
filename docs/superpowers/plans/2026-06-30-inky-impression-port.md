# Inky Impression 7.3" Weather Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3 app that fetches Google Maps Platform Weather forecasts and renders an 800×480 color image to a Raspberry Pi + Pimoroni Inky Impression 7.3", showing a 12-hour rolling hourly panel plus a 10-day forecast strip.

**Architecture:** A small package (`inky_weather/`) with three focused modules: `weather.py` (fetch + parse + pure helpers), `icons.py` (download/cache Google weather icons), and `render.py` (Pillow drawing, data-in → image-out). `main.py` orchestrates: load config → fetch → parse → render → push to display, with a `--fixture` mode for offline development on a Mac. Pure logic is TDD'd with pytest; rendering has smoke tests plus a fixture-to-PNG path for visual review.

**Tech Stack:** Python 3.9+, Pillow, requests, pytest, Pimoroni `inky` library, Google Maps Platform Weather API v1, cron.

**Reference:** Design spec at `docs/superpowers/specs/2026-06-30-inky-impression-port-design.md`.

---

## File Map

| File | Responsibility |
|---|---|
| `inky_weather/__init__.py` | Package marker |
| `inky_weather/config.example.py` | Template config (key, lat/long, location_name); real `config.py` is gitignored |
| `inky_weather/weather.py` | API fetch, JSON parse (hourly + daily), unit conversion, icon-name mapping, intensity/color helpers — pure & testable |
| `inky_weather/icons.py` | Download + cache weather icon PNGs from `iconBaseUri`, load/resize for rendering |
| `inky_weather/render.py` | Pillow drawing functions; compose the 800×480 image |
| `inky_weather/main.py` | Orchestration, CLI (`--fixture`, `--out`), error card, push to Inky |
| `inky_weather/fixtures/hourly_response.json` | Saved hourly API response for offline dev/tests |
| `inky_weather/fixtures/daily_response.json` | Saved daily API response for offline dev/tests |
| `inky_weather/assets/icons/` | Icon cache (gitignored) |
| `tests/test_weather.py` | Unit tests for `weather.py` |
| `tests/test_icons.py` | Unit tests for `icons.py` (mocked network) |
| `tests/test_render.py` | Smoke tests for `render.py` |
| `requirements.txt` | Runtime deps |
| `requirements-dev.txt` | Dev deps (pytest) |
| `.gitignore` | Ignore `config.py`, icon cache, `__pycache__`, out PNGs |
| `README-inky.md` | Setup, deploy, cron instructions |

**Data shapes** (produced by `weather.py`, consumed by `render.py`) — referenced throughout:

```python
# One hour (from parse_hourly), list of 12:
HourForecast = {
    "hour": int,          # 0-23 local
    "ampm_label": str,    # "10A", "2P"
    "is_daytime": bool,
    "condition": str,     # e.g. "PARTLY_CLOUDY"
    "icon_uri": str,      # weatherCondition.iconBaseUri
    "temp_f": int,        # rounded
    "feels_f": int,       # rounded
    "pop": int,           # 0-100
    "precip_type": str,   # "RAIN"/"SNOW"/...
    "thunder": int,       # 0-100
    "uv": int,
}

# One day (from parse_daily), list of up to 10:
DayForecast = {
    "name": str,          # "SAT"
    "icon_uri": str,      # daytime condition iconBaseUri
    "hi_f": int,
    "lo_f": int,
    "day":   {"pop": int, "precip_type": str, "qpf_mm": float, "thunder": int},
    "night": {"pop": int, "precip_type": str, "qpf_mm": float, "thunder": int},
}
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `inky_weather/__init__.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore` (append if exists)
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Create the package and requirements**

Create `inky_weather/__init__.py` (empty file).

Create `requirements.txt`:

```
Pillow>=10.0
requests>=2.28
inky>=1.5.0
```

Create `requirements-dev.txt`:

```
-r requirements.txt
pytest>=7.0
```

- [ ] **Step 2: Create `.gitignore` entries**

Ensure `.gitignore` contains (append these lines if the file already exists):

```
__pycache__/
*.pyc
inky_weather/config.py
inky_weather/assets/icons/
*.out.png
.pytest_cache/
```

- [ ] **Step 3: Add a smoke test to prove pytest works**

Create `tests/__init__.py` (empty file).

Create `tests/test_smoke.py`:

```python
def test_pytest_runs():
    assert True
```

- [ ] **Step 4: Install deps and run the smoke test**

Run:
```bash
pip3 install -r requirements-dev.txt
python3 -m pytest tests/test_smoke.py -v
```
Expected: 1 passed. (If `inky` fails to install on macOS due to GPIO deps, install it only on the Pi; for local dev run `pip3 install Pillow requests pytest` instead — `inky` is imported lazily in `main.py` so tests don't need it.)

- [ ] **Step 5: Commit**

```bash
git add inky_weather/__init__.py requirements.txt requirements-dev.txt .gitignore tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold inky_weather package and test setup"
```

---

### Task 2: Offline fixtures

**Files:**
- Create: `inky_weather/fixtures/hourly_response.json`
- Create: `inky_weather/fixtures/daily_response.json`

These let every parse/render test run without network or API quota.

- [ ] **Step 1: Create the hourly fixture**

Create `inky_weather/fixtures/hourly_response.json`. Reuse the existing project fixture content from `google_response.txt` (24 hours, `forecastHours` array). Copy it:

```bash
cp google_response.txt inky_weather/fixtures/hourly_response.json
```

Verify it is valid JSON with at least 12 entries:
```bash
python3 -c "import json;d=json.load(open('inky_weather/fixtures/hourly_response.json'));print(len(d['forecastHours']))"
```
Expected: a number ≥ 12 (e.g. 24).

- [ ] **Step 2: Create the daily fixture**

Create `inky_weather/fixtures/daily_response.json` with 10 days exercising every precip signature (popup storm, washout, overnight rain, dry, snow). Use the Google daily schema (`forecastDays` with `daytimeForecast`/`nighttimeForecast`):

```json
{
  "forecastDays": [
    {"interval":{"startTime":"2026-06-30T04:00:00Z","endTime":"2026-07-01T04:00:00Z"},"displayDate":{"year":2026,"month":6,"day":30},"maxTemperature":{"degrees":28.9,"unit":"CELSIUS"},"minTemperature":{"degrees":15.6,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"THUNDERSTORM","description":"Thunderstorm","iconBaseUri":"https://maps.gstatic.com/weather/v1/thunderstorm"},"precipitation":{"probability":{"percent":50,"type":"RAIN"},"qpf":{"quantity":2.0,"unit":"MILLIMETERS"}},"thunderstormProbability":55},"nighttimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Clear","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":10,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-01T04:00:00Z","endTime":"2026-07-02T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":1},"maxTemperature":{"degrees":23.3,"unit":"CELSIUS"},"minTemperature":{"degrees":16.7,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"HEAVY_RAIN","description":"Heavy Rain","iconBaseUri":"https://maps.gstatic.com/weather/v1/heavy_rain"},"precipitation":{"probability":{"percent":90,"type":"RAIN"},"qpf":{"quantity":12.0,"unit":"MILLIMETERS"}},"thunderstormProbability":5},"nighttimeForecast":{"weatherCondition":{"type":"RAIN","description":"Rain","iconBaseUri":"https://maps.gstatic.com/weather/v1/rain"},"precipitation":{"probability":{"percent":85,"type":"RAIN"},"qpf":{"quantity":9.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-02T04:00:00Z","endTime":"2026-07-03T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":2},"maxTemperature":{"degrees":26.1,"unit":"CELSIUS"},"minTemperature":{"degrees":12.8,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"MOSTLY_CLEAR","description":"Mostly Clear","iconBaseUri":"https://maps.gstatic.com/weather/v1/mostly_clear"},"precipitation":{"probability":{"percent":15,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"RAIN","description":"Rain","iconBaseUri":"https://maps.gstatic.com/weather/v1/rain"},"precipitation":{"probability":{"percent":80,"type":"RAIN"},"qpf":{"quantity":6.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-03T04:00:00Z","endTime":"2026-07-04T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":3},"maxTemperature":{"degrees":29.4,"unit":"CELSIUS"},"minTemperature":{"degrees":13.9,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Sunny","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":0,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Clear","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":0,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-04T04:00:00Z","endTime":"2026-07-05T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":4},"maxTemperature":{"degrees":21.1,"unit":"CELSIUS"},"minTemperature":{"degrees":10.0,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"SCATTERED_SHOWERS","description":"Scattered Showers","iconBaseUri":"https://maps.gstatic.com/weather/v1/scattered_showers"},"precipitation":{"probability":{"percent":55,"type":"RAIN"},"qpf":{"quantity":1.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"PARTLY_CLOUDY","description":"Partly Cloudy","iconBaseUri":"https://maps.gstatic.com/weather/v1/partly_cloudy"},"precipitation":{"probability":{"percent":30,"type":"RAIN"},"qpf":{"quantity":1.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-05T04:00:00Z","endTime":"2026-07-06T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":5},"maxTemperature":{"degrees":24.4,"unit":"CELSIUS"},"minTemperature":{"degrees":14.4,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"THUNDERSTORM","description":"Thunderstorm","iconBaseUri":"https://maps.gstatic.com/weather/v1/thunderstorm"},"precipitation":{"probability":{"percent":65,"type":"RAIN"},"qpf":{"quantity":4.0,"unit":"MILLIMETERS"}},"thunderstormProbability":40},"nighttimeForecast":{"weatherCondition":{"type":"RAIN_SHOWERS","description":"Rain Showers","iconBaseUri":"https://maps.gstatic.com/weather/v1/rain_showers"},"precipitation":{"probability":{"percent":55,"type":"RAIN"},"qpf":{"quantity":3.0,"unit":"MILLIMETERS"}},"thunderstormProbability":20}},
    {"interval":{"startTime":"2026-07-06T04:00:00Z","endTime":"2026-07-07T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":6},"maxTemperature":{"degrees":26.7,"unit":"CELSIUS"},"minTemperature":{"degrees":16.1,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"PARTLY_CLOUDY","description":"Partly Cloudy","iconBaseUri":"https://maps.gstatic.com/weather/v1/partly_cloudy"},"precipitation":{"probability":{"percent":20,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Clear","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":10,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-07T04:00:00Z","endTime":"2026-07-08T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":7},"maxTemperature":{"degrees":0.6,"unit":"CELSIUS"},"minTemperature":{"degrees":-4.4,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"SNOW","description":"Snow","iconBaseUri":"https://maps.gstatic.com/weather/v1/snow"},"precipitation":{"probability":{"percent":70,"type":"SNOW"},"qpf":{"quantity":8.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"SNOW_SHOWERS","description":"Snow Showers","iconBaseUri":"https://maps.gstatic.com/weather/v1/snow_showers"},"precipitation":{"probability":{"percent":60,"type":"SNOW"},"qpf":{"quantity":5.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-08T04:00:00Z","endTime":"2026-07-09T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":8},"maxTemperature":{"degrees":14.4,"unit":"CELSIUS"},"minTemperature":{"degrees":4.4,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"CLOUDY","description":"Cloudy","iconBaseUri":"https://maps.gstatic.com/weather/v1/cloudy"},"precipitation":{"probability":{"percent":35,"type":"RAIN"},"qpf":{"quantity":1.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"RAIN","description":"Rain","iconBaseUri":"https://maps.gstatic.com/weather/v1/rain"},"precipitation":{"probability":{"percent":75,"type":"RAIN"},"qpf":{"quantity":7.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}},
    {"interval":{"startTime":"2026-07-09T04:00:00Z","endTime":"2026-07-10T04:00:00Z"},"displayDate":{"year":2026,"month":7,"day":9},"maxTemperature":{"degrees":22.2,"unit":"CELSIUS"},"minTemperature":{"degrees":7.8,"unit":"CELSIUS"},"daytimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Sunny","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":5,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0},"nighttimeForecast":{"weatherCondition":{"type":"CLEAR","description":"Clear","iconBaseUri":"https://maps.gstatic.com/weather/v1/clear"},"precipitation":{"probability":{"percent":5,"type":"RAIN"},"qpf":{"quantity":0.0,"unit":"MILLIMETERS"}},"thunderstormProbability":0}}
  ]
}
```

- [ ] **Step 2b: Verify the daily fixture is valid**

Run:
```bash
python3 -c "import json;d=json.load(open('inky_weather/fixtures/daily_response.json'));print(len(d['forecastDays']))"
```
Expected: `10`

- [ ] **Step 3: Commit**

```bash
git add inky_weather/fixtures/hourly_response.json inky_weather/fixtures/daily_response.json
git commit -m "test: add hourly and daily API fixtures for offline dev"
```

---

### Task 3: Temperature conversion

**Files:**
- Create: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_weather.py`:

```python
from inky_weather import weather


def test_c_to_f_freezing():
    assert weather.c_to_f(0) == 32


def test_c_to_f_rounds_to_int():
    # 24.5 C = 76.1 F -> 76
    assert weather.c_to_f(24.5) == 76


def test_c_to_f_negative():
    # -4.4 C = 24.08 F -> 24
    assert weather.c_to_f(-4.4) == 24
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -v`
Expected: FAIL — `ModuleNotFoundError` or `AttributeError: module 'inky_weather.weather' has no attribute 'c_to_f'`.

- [ ] **Step 3: Write the minimal implementation**

Create `inky_weather/weather.py`:

```python
"""Fetch and parse Google Maps Platform Weather forecasts; pure helpers."""


def c_to_f(celsius):
    """Convert Celsius to Fahrenheit, rounded to the nearest int."""
    return round(celsius * 9 / 5 + 32)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add c_to_f temperature conversion"
```

---

### Task 4: Hour label formatting

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:

```python
def test_hour_label_midnight():
    assert weather.hour_label(0) == "12A"


def test_hour_label_noon():
    assert weather.hour_label(12) == "12P"


def test_hour_label_morning():
    assert weather.hour_label(6) == "6A"


def test_hour_label_evening():
    assert weather.hour_label(15) == "3P"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k hour_label -v`
Expected: FAIL — no attribute `hour_label`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py`:

```python
def hour_label(hour):
    """Format a 0-23 hour as a compact label like '12A', '6A', '3P'."""
    suffix = "A" if hour < 12 else "P"
    h12 = hour % 12
    if h12 == 0:
        h12 = 12
    return "{}{}".format(h12, suffix)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k hour_label -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add hour_label formatting"
```

---

### Task 5: Precipitation intensity level

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:

```python
def test_intensity_dry_when_no_pop():
    assert weather.intensity_level(qpf_mm=5.0, pop=0) == 0


def test_intensity_dry_when_no_qpf():
    assert weather.intensity_level(qpf_mm=0.0, pop=80) == 0


def test_intensity_light():
    assert weather.intensity_level(qpf_mm=1.0, pop=60) == 1


def test_intensity_moderate():
    assert weather.intensity_level(qpf_mm=5.0, pop=80) == 2


def test_intensity_heavy():
    assert weather.intensity_level(qpf_mm=12.0, pop=90) == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k intensity -v`
Expected: FAIL — no attribute `intensity_level`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py`:

```python
def intensity_level(qpf_mm, pop):
    """Map precip amount (mm) to pip level 0-3.

    0 = none/dry, 1 = light (<2.5mm), 2 = moderate (2.5-7.5mm), 3 = heavy (>7.5mm).
    Returns 0 when there is effectively no precip chance or no accumulation.
    """
    if pop < 5 or qpf_mm <= 0:
        return 0
    if qpf_mm < 2.5:
        return 1
    if qpf_mm < 7.5:
        return 2
    return 3
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k intensity -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add intensity_level pip mapping from QPF"
```

---

### Task 6: Precipitation color classification

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

This returns a semantic name; `render.py` maps names to RGB. Keeping it a string keeps `weather.py` free of rendering concerns and easy to test.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:

```python
def test_precip_kind_dry():
    assert weather.precip_kind(pop=0, precip_type="RAIN", thunder=0) == "dry"


def test_precip_kind_thunderstorm_takes_priority():
    assert weather.precip_kind(pop=60, precip_type="RAIN", thunder=40) == "storm"


def test_precip_kind_snow():
    assert weather.precip_kind(pop=70, precip_type="SNOW", thunder=0) == "snow"


def test_precip_kind_rain():
    assert weather.precip_kind(pop=80, precip_type="RAIN", thunder=10) == "rain"


def test_precip_kind_wintry_mix():
    assert weather.precip_kind(pop=50, precip_type="SLEET", thunder=0) == "mix"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k precip_kind -v`
Expected: FAIL — no attribute `precip_kind`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py`:

```python
def precip_kind(pop, precip_type, thunder):
    """Classify a precip cell into a semantic kind for coloring.

    Returns one of: 'dry', 'storm', 'snow', 'mix', 'rain'.
    Thunderstorm dominance (>=30%) takes priority over type.
    """
    if pop < 5:
        return "dry"
    if thunder >= 30:
        return "storm"
    if precip_type == "SNOW":
        return "snow"
    if precip_type in ("SLEET", "ICE", "FREEZING_RAIN"):
        return "mix"
    return "rain"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k precip_kind -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add precip_kind semantic classification"
```

---

### Task 7: Parse hourly forecast

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py` (add `import json` and `import os` at the top of the file if not present):

```python
import json
import os

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name)) as f:
        return json.load(f)


def test_parse_hourly_returns_twelve():
    data = _load_fixture("hourly_response.json")
    hours = weather.parse_hourly(data, count=12)
    assert len(hours) == 12


def test_parse_hourly_first_hour_fields():
    data = _load_fixture("hourly_response.json")
    first = weather.parse_hourly(data, count=12)[0]
    # From fixture hour 0: 24.5C=76F, PARTLY_CLOUDY, pop 20, uv 6, daytime
    assert first["temp_f"] == 76
    assert first["feels_f"] == 77          # 25.0C -> 77
    assert first["condition"] == "PARTLY_CLOUDY"
    assert first["pop"] == 20
    assert first["precip_type"] == "RAIN"
    assert first["thunder"] == 0
    assert first["uv"] == 6
    assert first["is_daytime"] is True
    assert first["ampm_label"] == "10A"    # displayDateTime.hours == 10
    assert first["icon_uri"].endswith("/partly_cloudy")


def test_parse_hourly_handles_short_list():
    data = {"forecastHours": _load_fixture("hourly_response.json")["forecastHours"][:3]}
    hours = weather.parse_hourly(data, count=12)
    assert len(hours) == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k parse_hourly -v`
Expected: FAIL — no attribute `parse_hourly`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py`:

```python
def parse_hourly(data, count=12):
    """Extract the first `count` hours from a Google hourly response.

    Returns a list of HourForecast dicts (see plan header for shape).
    """
    hours = []
    for obj in data.get("forecastHours", [])[:count]:
        cond = obj.get("weatherCondition", {})
        precip = obj.get("precipitation", {})
        prob = precip.get("probability", {})
        hour = obj.get("displayDateTime", {}).get("hours", 0)
        hours.append({
            "hour": hour,
            "ampm_label": hour_label(hour),
            "is_daytime": obj.get("isDaytime", True),
            "condition": cond.get("type", "UNKNOWN"),
            "icon_uri": cond.get("iconBaseUri", ""),
            "temp_f": c_to_f(obj.get("temperature", {}).get("degrees", 0)),
            "feels_f": c_to_f(obj.get("feelsLikeTemperature", {}).get("degrees", 0)),
            "pop": prob.get("percent", 0),
            "precip_type": prob.get("type", "RAIN"),
            "thunder": obj.get("thunderstormProbability", 0),
            "uv": obj.get("uvIndex", 0),
        })
    return hours
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k parse_hourly -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add parse_hourly"
```

---

### Task 8: Parse daily forecast

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:

```python
def test_parse_daily_returns_ten():
    data = _load_fixture("daily_response.json")
    days = weather.parse_daily(data, count=10)
    assert len(days) == 10


def test_parse_daily_first_day_fields():
    data = _load_fixture("daily_response.json")
    first = weather.parse_daily(data, count=10)[0]
    # Day 0: 2026-06-30 is a Tuesday; 28.9C->84F hi, 15.6C->60F lo
    assert first["name"] == "TUE"
    assert first["hi_f"] == 84
    assert first["lo_f"] == 60
    assert first["day"]["pop"] == 50
    assert first["day"]["thunder"] == 55
    assert first["day"]["qpf_mm"] == 2.0
    assert first["night"]["pop"] == 10
    assert first["icon_uri"].endswith("/thunderstorm")


def test_parse_daily_snow_day():
    data = _load_fixture("daily_response.json")
    days = weather.parse_daily(data, count=10)
    snow_day = days[7]  # 2026-07-07 snow entry
    assert snow_day["day"]["precip_type"] == "SNOW"
    assert snow_day["hi_f"] == 33   # 0.6C -> 33
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k parse_daily -v`
Expected: FAIL — no attribute `parse_daily`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py` (add `import datetime` at the top of the file):

```python
import datetime

_WEEKDAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _day_name(display_date):
    """Return a 3-letter weekday from a Google displayDate dict."""
    d = datetime.date(display_date["year"], display_date["month"], display_date["day"])
    return _WEEKDAY[d.weekday()]


def _parse_precip_block(block):
    """Extract precip fields from a daytimeForecast/nighttimeForecast object."""
    precip = block.get("precipitation", {})
    prob = precip.get("probability", {})
    return {
        "pop": prob.get("percent", 0),
        "precip_type": prob.get("type", "RAIN"),
        "qpf_mm": precip.get("qpf", {}).get("quantity", 0.0),
        "thunder": block.get("thunderstormProbability", 0),
    }


def parse_daily(data, count=10):
    """Extract the first `count` days from a Google daily response.

    Returns a list of DayForecast dicts (see plan header for shape).
    """
    days = []
    for obj in data.get("forecastDays", [])[:count]:
        day_block = obj.get("daytimeForecast", {})
        night_block = obj.get("nighttimeForecast", {})
        cond = day_block.get("weatherCondition", {})
        days.append({
            "name": _day_name(obj["displayDate"]),
            "icon_uri": cond.get("iconBaseUri", ""),
            "hi_f": c_to_f(obj.get("maxTemperature", {}).get("degrees", 0)),
            "lo_f": c_to_f(obj.get("minTemperature", {}).get("degrees", 0)),
            "day": _parse_precip_block(day_block),
            "night": _parse_precip_block(night_block),
        })
    return days
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k parse_daily -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add parse_daily with day/night precip blocks"
```

---

### Task 9: Fetch functions (URLs + fixture loader)

**Files:**
- Modify: `inky_weather/weather.py`
- Test: `tests/test_weather.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_weather.py`:

```python
def test_hourly_url_contains_params():
    url = weather.hourly_url(lat="37.2", long="-80.0", key="ABC", hours=12)
    assert "location.latitude=37.2" in url
    assert "location.longitude=-80.0" in url
    assert "hours=12" in url
    assert "key=ABC" in url


def test_daily_url_contains_params():
    url = weather.daily_url(lat="37.2", long="-80.0", key="ABC", days=10)
    assert "days=10" in url
    assert "key=ABC" in url


def test_load_fixtures_returns_parsed():
    hours, days = weather.load_from_fixtures(FIXTURE_DIR)
    assert len(hours) == 12
    assert len(days) == 10
    assert hours[0]["temp_f"] == 76
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_weather.py -k "url or load_fixtures" -v`
Expected: FAIL — no attribute `hourly_url`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/weather.py` (add `import os` and `import requests` at the top):

```python
import os
import requests

_HOURLY_ENDPOINT = "https://weather.googleapis.com/v1/forecast/hours:lookup"
_DAILY_ENDPOINT = "https://weather.googleapis.com/v1/forecast/days:lookup"


def hourly_url(lat, long, key, hours=12):
    return (
        "{base}?key={key}&location.latitude={lat}&location.longitude={long}"
        "&hours={hours}&unitsSystem=METRIC"
    ).format(base=_HOURLY_ENDPOINT, key=key, lat=lat, long=long, hours=hours)


def daily_url(lat, long, key, days=10):
    return (
        "{base}?key={key}&location.latitude={lat}&location.longitude={long}"
        "&days={days}&unitsSystem=METRIC"
    ).format(base=_DAILY_ENDPOINT, key=key, lat=lat, long=long, days=days)


def fetch_live(lat, long, key, hours=12, days=10, timeout=20):
    """Fetch and parse both forecasts from the live API. Returns (hours, days)."""
    hourly_resp = requests.get(hourly_url(lat, long, key, hours), timeout=timeout)
    hourly_resp.raise_for_status()
    daily_resp = requests.get(daily_url(lat, long, key, days), timeout=timeout)
    daily_resp.raise_for_status()
    return (
        parse_hourly(hourly_resp.json(), count=hours),
        parse_daily(daily_resp.json(), count=days),
    )


def load_from_fixtures(fixture_dir, hours=12, days=10):
    """Load and parse both forecasts from local fixture files. Returns (hours, days)."""
    import json
    with open(os.path.join(fixture_dir, "hourly_response.json")) as f:
        hourly = json.load(f)
    with open(os.path.join(fixture_dir, "daily_response.json")) as f:
        daily = json.load(f)
    return parse_hourly(hourly, count=hours), parse_daily(daily, count=days)
```

> Note: `unitsSystem=METRIC` keeps temperatures in Celsius so `c_to_f` handles conversion consistently. Verify the exact endpoint hostnames against the live API on first real run (Task 19); the parse layer is unaffected by URL shape.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_weather.py -k "url or load_fixtures" -v`
Expected: 3 passed. Then run the whole file: `python3 -m pytest tests/test_weather.py -v` — all pass.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/weather.py tests/test_weather.py
git commit -m "feat: add fetch URLs, live fetch, and fixture loader"
```

---

### Task 10: Icon download + cache

**Files:**
- Create: `inky_weather/icons.py`
- Test: `tests/test_icons.py`

Google returns a PNG when you append `.png` to `iconBaseUri`. We download once, cache to disk, and load/resize on demand. Tests mock the network so they never hit Google.

- [ ] **Step 1: Write the failing test**

Create `tests/test_icons.py`:

```python
import os
from unittest import mock

from PIL import Image

from inky_weather import icons


def test_cache_path_from_uri(tmp_path):
    p = icons.cache_path("https://maps.gstatic.com/weather/v1/partly_cloudy", str(tmp_path))
    assert p.endswith("partly_cloudy.png")
    assert str(tmp_path) in p


def test_get_icon_downloads_once_then_caches(tmp_path):
    uri = "https://maps.gstatic.com/weather/v1/clear"
    fake_png = _tiny_png_bytes()
    with mock.patch("inky_weather.icons.requests.get") as m:
        m.return_value.content = fake_png
        m.return_value.raise_for_status = lambda: None
        img1 = icons.get_icon(uri, size=40, cache_dir=str(tmp_path))
        img2 = icons.get_icon(uri, size=40, cache_dir=str(tmp_path))
    assert m.call_count == 1                      # second call used the cache
    assert img1.size == (40, 40)
    assert img2.size == (40, 40)


def test_get_icon_missing_uri_returns_placeholder(tmp_path):
    img = icons.get_icon("", size=40, cache_dir=str(tmp_path))
    assert img.size == (40, 40)


def _tiny_png_bytes():
    import io
    buf = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_icons.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inky_weather.icons'`.

- [ ] **Step 3: Write the implementation**

Create `inky_weather/icons.py`:

```python
"""Download, cache, and load Google weather icons from iconBaseUri."""
import os

import requests
from PIL import Image


def cache_path(icon_uri, cache_dir):
    """Local cache filename for an icon URI (last path segment + .png)."""
    name = icon_uri.rstrip("/").rsplit("/", 1)[-1] or "unknown"
    return os.path.join(cache_dir, name + ".png")


def _download(icon_uri, dest):
    resp = requests.get(icon_uri + ".png", timeout=20)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def get_icon(icon_uri, size, cache_dir):
    """Return an RGBA PIL image for the given icon URI, resized to size×size.

    Downloads and caches on first use. Returns a blank transparent image if the
    URI is empty or the download/open fails (so rendering never crashes).
    """
    os.makedirs(cache_dir, exist_ok=True)
    blank = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if not icon_uri:
        return blank
    path = cache_path(icon_uri, cache_dir)
    try:
        if not os.path.exists(path):
            _download(icon_uri, path)
        img = Image.open(path).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)
    except (requests.RequestException, OSError):
        return blank
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_icons.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/icons.py tests/test_icons.py
git commit -m "feat: add icon download and disk cache"
```

---

### Task 11: Render constants and palette

**Files:**
- Create: `inky_weather/render.py`
- Test: `tests/test_render.py`

Draw in RGB using colors close to the Inky palette; the `inky` library quantizes to the panel's 6/7 colors when pushed. `COLOR_STORM` defaults to red so it survives on the 6-color (no-orange) panel.

- [ ] **Step 1: Write the failing test**

Create `tests/test_render.py`:

```python
from inky_weather import render


def test_dimensions():
    assert render.WIDTH == 800
    assert render.HEIGHT == 480


def test_kind_color_known_kinds():
    for kind in ("dry", "rain", "storm", "snow", "mix"):
        c = render.kind_color(kind)
        assert isinstance(c, tuple) and len(c) == 3


def test_temp_color_hot_is_red_ish():
    r, g, b = render.temp_color(95)
    assert r > b            # warm -> more red than blue
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inky_weather.render'`.

- [ ] **Step 3: Write the implementation**

Create `inky_weather/render.py`:

```python
"""Pillow rendering for the Inky Impression weather display."""
from PIL import Image, ImageDraw, ImageFont

WIDTH = 800
HEIGHT = 480

# Palette-friendly RGB colors (quantized to the panel by the inky library).
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
PAPER = (255, 255, 255)      # background
RED = (200, 30, 30)
BLUE = (30, 70, 200)
GREEN = (30, 140, 60)
YELLOW = (230, 190, 0)
ORANGE = (230, 120, 0)

# Semantic mapping. Storm defaults to RED so it reads on 6-color panels.
COLOR_RAIN = BLUE
COLOR_STORM = RED
COLOR_SNOW = GREEN          # distinct from rain on a limited palette
COLOR_MIX = GREEN
COLOR_DRY = (210, 210, 210)


def kind_color(kind):
    """RGB for a precip kind name from weather.precip_kind()."""
    return {
        "rain": COLOR_RAIN,
        "storm": COLOR_STORM,
        "snow": COLOR_SNOW,
        "mix": COLOR_MIX,
        "dry": COLOR_DRY,
    }.get(kind, COLOR_RAIN)


def temp_color(temp_f):
    """Warm temps -> red, cool -> blue. Simple two-stop ramp."""
    if temp_f >= 78:
        return RED
    if temp_f >= 60:
        return BLACK
    return BLUE
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add render palette and color helpers"
```

---

### Task 12: Font loading helper

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def test_load_font_returns_font():
    f = render.load_font(14)
    # Pillow font objects expose getbbox
    assert hasattr(f, "getbbox")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k load_font -v`
Expected: FAIL — no attribute `load_font`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size):
    """Load a bold TrueType font at the given size, falling back to default."""
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k load_font -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add cross-platform font loader"
```

---

### Task 13: Text-centering helper

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py` (add `from PIL import Image, ImageDraw` at top):

```python
from PIL import Image, ImageDraw


def test_draw_centered_text_runs():
    img = Image.new("RGB", (100, 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    # Should not raise, and should change some pixels
    render.draw_centered_text(d, "Hi", 50, 20, render.load_font(14), (0, 0, 0))
    assert img.getpixel((50, 20)) != (255, 255, 255) or img.tobytes() != Image.new("RGB", (100, 40), (255, 255, 255)).tobytes()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k centered_text -v`
Expected: FAIL — no attribute `draw_centered_text`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
def draw_centered_text(draw, text, cx, cy, font, color):
    """Draw text horizontally centered on cx and vertically centered on cy."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), text, font=font, fill=color)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k centered_text -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add draw_centered_text helper"
```

---

### Task 14: Layout constants

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def test_layout_zones_sum_to_height():
    L = render.LAYOUT
    # hourly vertical zones fill the area below the header
    total = (L["header_h"] + L["temp_h"] + L["feels_h"]
             + L["precip_h"] + L["uv_h"] + L["hour_h"])
    assert total == render.HEIGHT


def test_layout_widths():
    L = render.LAYOUT
    assert L["hourly_w"] + L["daily_w"] == render.WIDTH
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k layout -v`
Expected: FAIL — no attribute `LAYOUT`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
# Layout geometry (pixels). Hourly zones (below header) sum to HEIGHT.
LAYOUT = {
    "header_h": 30,
    "temp_h": 250,
    "feels_h": 18,
    "precip_h": 80,
    "uv_h": 22,
    "hour_h": 80,          # 30+250+18+80+22+80 = 480
    "daily_w": 215,
    "hourly_w": WIDTH - 215,
    "num_hours": 12,
    "num_days": 10,
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k layout -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add render layout constants"
```

---

### Task 15: Draw the header

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

From here, rendering functions draw onto a shared image/draw. Tests assert they run and mark pixels rather than pixel-perfect output; visual review happens via the fixture PNG in Task 20.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def _blank():
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.PAPER)
    return img, ImageDraw.Draw(img)


def test_draw_header_marks_top_band():
    img, d = _blank()
    render.draw_header(d, "Blacksburg, VA", "Tue Jun 30", "10:02 AM")
    # header band should have non-paper pixels near the top
    assert any(img.getpixel((x, 10)) != render.PAPER for x in range(0, render.WIDTH, 20))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k draw_header -v`
Expected: FAIL — no attribute `draw_header`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
def draw_header(draw, location_name, date_str, updated_str):
    """Draw the top header band: location · date (left), updated (center)."""
    L = LAYOUT
    draw.rectangle([0, 0, WIDTH, L["header_h"]], fill=BLACK)
    font = load_font(15)
    left = location_name + " · " + date_str if location_name else date_str
    draw.text((10, L["header_h"] / 2 - 8), left, font=font, fill=WHITE)
    updated = "Updated " + updated_str
    draw_centered_text(draw, updated, L["hourly_w"] / 2 + 120, L["header_h"] / 2,
                       load_font(12), (200, 200, 200))
    draw_centered_text(draw, "10-DAY FORECAST", L["hourly_w"] + L["daily_w"] / 2,
                       L["header_h"] / 2, load_font(11), (210, 210, 210))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k draw_header -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: draw header band"
```

---

### Task 16: Draw the hourly panel (temp graph, feels, precip, UV, hours, night shading)

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

This is the largest render unit. It composes the left panel from a parsed hours list plus loaded icons. Icons are passed in (a list parallel to hours) so this function stays free of network I/O and is testable with blank images.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def _sample_hours():
    from inky_weather import weather
    import os, json
    fx = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")
    with open(os.path.join(fx, "hourly_response.json")) as f:
        return weather.parse_hourly(json.load(f), count=12)


def test_draw_hourly_panel_runs_and_marks():
    img, d = _blank()
    hours = _sample_hours()
    blank_icon = Image.new("RGBA", (34, 34), (0, 0, 0, 0))
    icons = [blank_icon] * len(hours)
    render.draw_hourly_panel(img, d, hours, icons)
    # precip zone should have some blue/red bar pixels somewhere in the panel
    L = render.LAYOUT
    changed = sum(
        1 for x in range(0, L["hourly_w"], 5)
        for y in range(L["header_h"], render.HEIGHT, 5)
        if img.getpixel((x, y)) != render.PAPER
    )
    assert changed > 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k hourly_panel -v`
Expected: FAIL — no attribute `draw_hourly_panel`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py` (add `from . import weather` at the top of the file):

```python
from . import weather


def draw_hourly_panel(img, draw, hours, icons):
    """Draw the left hourly panel. `icons` is a list of RGBA images parallel to hours."""
    L = LAYOUT
    n = L["num_hours"]
    col_w = L["hourly_w"] / n
    temp_y = L["header_h"]
    feels_y = temp_y + L["temp_h"]
    precip_y = feels_y + L["feels_h"]
    uv_y = precip_y + L["precip_h"]
    hour_y = uv_y + L["uv_h"]

    temps = [h["temp_f"] for h in hours]
    min_t, max_t = min(temps), max(temps)
    t_range = (max_t - min_t) or 1

    small = load_font(12)
    tiny = load_font(11)

    # Night shading (full panel height)
    for i, h in enumerate(hours):
        if not h["is_daytime"]:
            x0 = int(i * col_w)
            draw.rectangle([x0, L["header_h"], int(x0 + col_w), HEIGHT],
                           fill=(225, 227, 240))

    # Temperature graph: icon positioned by temp, label below
    icon_sz = 34
    usable = L["temp_h"] - icon_sz - 22
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        norm = (h["temp_f"] - min_t) / t_range
        icon_top = temp_y + usable * (1 - norm) + 4
        icons[i] and img.paste(icons[i], (int(cx - icon_sz / 2), int(icon_top)), icons[i])
        draw_centered_text(draw, "{}°".format(h["temp_f"]),
                           cx, icon_top + icon_sz + 10, small, temp_color(h["temp_f"]))

    # Feels-like row
    draw.line([0, feels_y, L["hourly_w"], feels_y], fill=(180, 180, 180))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        draw_centered_text(draw, "FL {}°".format(h["feels_f"]),
                           cx, feels_y + L["feels_h"] / 2, tiny, (100, 100, 100))

    # Precip probability bars
    draw.line([0, precip_y, L["hourly_w"], precip_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        bar_h = max(2, int((h["pop"] / 100) * (L["precip_h"] - 4)))
        bar_top = precip_y + L["precip_h"] - bar_h
        color = COLOR_STORM if h["thunder"] > 30 else COLOR_RAIN
        draw.rectangle([int(i * col_w + 3), bar_top, int((i + 1) * col_w - 3),
                        precip_y + L["precip_h"]], fill=color)
        if h["pop"] > 0:
            draw_centered_text(draw, "{}%".format(h["pop"]), cx, bar_top + 8,
                               load_font(10), WHITE)
        if h["thunder"] >= 30:
            draw_centered_text(draw, "⚡", cx, precip_y + 8, load_font(12), YELLOW)

    # UV row
    draw.line([0, uv_y, L["hourly_w"], uv_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        uv_col = RED if h["uv"] >= 6 else (GREEN if h["uv"] < 3 else ORANGE)
        draw_centered_text(draw, "UV {}".format(h["uv"]), cx, uv_y + L["uv_h"] / 2,
                           tiny, uv_col)

    # Hour labels
    draw.line([0, hour_y, L["hourly_w"], hour_y], fill=(150, 150, 150))
    for i, h in enumerate(hours):
        cx = i * col_w + col_w / 2
        draw_centered_text(draw, h["ampm_label"], cx, hour_y + 14, small, BLACK)

    # Vertical divider between panels
    draw.rectangle([L["hourly_w"], 0, L["hourly_w"] + 2, HEIGHT], fill=BLACK)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k hourly_panel -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: draw hourly panel (temp/feels/precip/uv/hours)"
```

---

### Task 17: Draw one daily row

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

Factor a single-row function first; the strip (Task 18) loops it. Precip bars use `weather.precip_kind` + `kind_color` and `weather.intensity_level` for pips.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def _sample_days():
    from inky_weather import weather
    import os, json
    fx = os.path.join(os.path.dirname(__file__), "..", "inky_weather", "fixtures")
    with open(os.path.join(fx, "daily_response.json")) as f:
        return weather.parse_daily(json.load(f), count=10)


def test_draw_daily_row_runs():
    img, d = _blank()
    day = _sample_days()[0]
    blank_icon = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
    # global scale
    render.draw_daily_row(img, d, day, y=40, row_h=45, icon=blank_icon,
                          global_lo=10, global_hi=90)
    L = render.LAYOUT
    changed = any(
        img.getpixel((x, y)) != render.PAPER
        for x in range(L["hourly_w"] + 4, render.WIDTH, 5)
        for y in range(40, 85, 5)
    )
    assert changed
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k daily_row -v`
Expected: FAIL — no attribute `draw_daily_row`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
def _draw_precip_bar(draw, x, y, track_w, label, cell, font_tiny):
    """One horizontal precip bar: label, filled track (len=pop), %, pips."""
    kind = weather.precip_kind(cell["pop"], cell["precip_type"], cell["thunder"])
    color = kind_color(kind)
    track_h = 12
    draw.text((x, y + 1), label, font=font_tiny, fill=(120, 120, 120))
    tx = x + 12
    draw.rectangle([tx, y, tx + track_w, y + track_h], fill=(225, 221, 210))
    fill_w = int((cell["pop"] / 100) * track_w)
    if kind != "dry" and fill_w > 0:
        draw.rectangle([tx, y, tx + fill_w, y + track_h], fill=color)
    draw.text((tx + track_w - 26, y + 1), "{}%".format(cell["pop"]),
              font=font_tiny, fill=(70, 70, 70) if fill_w < track_w * 0.55 else WHITE)
    # thunderstorm marker
    mx = tx + track_w + 4
    if cell["thunder"] >= 30:
        draw.text((mx, y), "⚡", font=font_tiny, fill=ORANGE)
        mx += 10
    # intensity pips
    level = weather.intensity_level(cell["qpf_mm"], cell["pop"])
    for p in range(3):
        pc = color if p < level else (216, 210, 196)
        px = mx + p * 7
        draw.ellipse([px, y + 4, px + 4, y + 8], fill=pc)


def draw_daily_row(img, draw, day, y, row_h, icon, global_lo, global_hi):
    """Draw one day's row in the right strip."""
    L = LAYOUT
    strip_x = L["hourly_w"] + 2
    strip_w = L["daily_w"] - 2
    tiny = load_font(11)
    micro = load_font(10)

    # icon + name (left column)
    if icon:
        img.paste(icon, (strip_x + 6, int(y + row_h / 2 - 16)), icon)
    draw_centered_text(draw, day["name"], strip_x + 20, y + row_h - 8, micro, BLACK)

    content_x = strip_x + 40
    content_w = strip_w - 42

    # temperature spread bar (shared scale) with inline lo/hi
    g_range = (global_hi - global_lo) or 1
    t_bar_x = content_x + 20
    t_bar_w = content_w - 40
    t_bar_y = y + 6
    t_bar_h = 8
    draw.text((content_x, t_bar_y - 1), "{}°".format(day["lo_f"]), font=micro, fill=BLUE)
    draw.rectangle([t_bar_x, t_bar_y, t_bar_x + t_bar_w, t_bar_y + t_bar_h], fill=(215, 215, 215))
    seg_l = int(((day["lo_f"] - global_lo) / g_range) * t_bar_w)
    seg_r = int(((day["hi_f"] - global_lo) / g_range) * t_bar_w)
    draw.rectangle([t_bar_x + seg_l, t_bar_y, t_bar_x + seg_r, t_bar_y + t_bar_h],
                   fill=temp_color(day["hi_f"]))
    draw.text((t_bar_x + t_bar_w + 3, t_bar_y - 1), "{}°".format(day["hi_f"]),
              font=micro, fill=RED)

    # stacked day / night precip bars
    p_track_w = content_w - 70
    _draw_precip_bar(draw, content_x, y + 18, p_track_w, "D", day["day"], tiny)
    _draw_precip_bar(draw, content_x, y + 31, p_track_w, "N", day["night"], tiny)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k daily_row -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: draw a single daily row with spread bar and D/N precip"
```

---

### Task 18: Draw the daily strip + compose full image

**Files:**
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
def test_render_display_returns_image():
    hours = _sample_hours()
    days = _sample_days()
    hour_icons = [Image.new("RGBA", (34, 34), (0, 0, 0, 0))] * len(hours)
    day_icons = [Image.new("RGBA", (26, 26), (0, 0, 0, 0))] * len(days)
    img = render.render_display(
        hours, days, hour_icons, day_icons,
        location_name="Blacksburg, VA", date_str="Tue Jun 30", updated_str="10:02 AM",
    )
    assert img.size == (render.WIDTH, render.HEIGHT)
    # right strip should have marks
    L = render.LAYOUT
    assert any(img.getpixel((L["hourly_w"] + 30, y)) != render.PAPER
               for y in range(render.HEIGHT))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k render_display -v`
Expected: FAIL — no attribute `render_display`.

- [ ] **Step 3: Write the implementation**

Add to `inky_weather/render.py`:

```python
def draw_daily_strip(img, draw, days, icons):
    """Draw all daily rows in the right strip using a shared temperature scale."""
    L = LAYOUT
    strip_x = L["hourly_w"] + 2
    strip_w = L["daily_w"] - 2
    row_h = (HEIGHT - L["header_h"]) / len(days)
    global_lo = min(d["lo_f"] for d in days)
    global_hi = max(d["hi_f"] for d in days)
    for i, day in enumerate(days):
        y = int(L["header_h"] + i * row_h)
        if i > 0:
            draw.line([strip_x, y, strip_x + strip_w, y], fill=(205, 200, 186))
        draw_daily_row(img, draw, day, y, row_h, icons[i], global_lo, global_hi)


def render_display(hours, days, hour_icons, day_icons,
                   location_name, date_str, updated_str):
    """Compose the full 800x480 image. Returns an RGB PIL Image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw_hourly_panel(img, draw, hours, hour_icons)
    draw_daily_strip(img, draw, days, day_icons)
    draw_header(draw, location_name, date_str, updated_str)
    return img
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k render_display -v`
Expected: 1 passed. Then run the full suite: `python3 -m pytest -v` — all pass.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: draw daily strip and compose full display image"
```

---

### Task 19: Config template + error card

**Files:**
- Create: `inky_weather/config.example.py`
- Modify: `inky_weather/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Create the config template**

Create `inky_weather/config.example.py`:

```python
# Copy to config.py and fill in real values. config.py is gitignored.
config = {
    "google_weather_key": "YOUR_GOOGLE_MAPS_PLATFORM_WEATHER_KEY",
    "lat": "37.21350",
    "long": "-80.03739",
    "location_name": "Blacksburg, VA",   # header label; set to "" to hide
}
```

- [ ] **Step 2: Write the failing test for the error card**

Add to `tests/test_render.py`:

```python
def test_render_error_card_returns_image():
    img = render.render_error("No network: fetch failed")
    assert img.size == (render.WIDTH, render.HEIGHT)
    # message area should have dark pixels
    assert any(img.getpixel((x, render.HEIGHT // 2)) != render.PAPER
               for x in range(0, render.WIDTH, 10))
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_render.py -k error_card -v`
Expected: FAIL — no attribute `render_error`.

- [ ] **Step 4: Write the implementation**

Add to `inky_weather/render.py`:

```python
def render_error(message):
    """Render a simple full-screen error card so failures are visible on-panel."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, LAYOUT["header_h"]], fill=RED)
    draw.text((10, 7), "Weather update failed", font=load_font(15), fill=WHITE)
    draw_centered_text(draw, message, WIDTH / 2, HEIGHT / 2, load_font(18), BLACK)
    draw_centered_text(draw, "Will retry next hour", WIDTH / 2, HEIGHT / 2 + 34,
                       load_font(13), (110, 110, 110))
    return img
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_render.py -k error_card -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/config.example.py inky_weather/render.py tests/test_render.py
git commit -m "feat: add config template and error card renderer"
```

---

### Task 20: Orchestration (`main.py`) with `--fixture` mode

**Files:**
- Create: `inky_weather/main.py`
- Test: manual (fixture render to PNG)

`main.py` is the only module that touches the network and the display, so it has no unit tests; it is verified by rendering the fixtures to a PNG for visual review, then on-device.

- [ ] **Step 1: Write `main.py`**

Create `inky_weather/main.py`:

```python
"""Entry point: fetch forecasts, render the display, push to Inky (or PNG)."""
import argparse
import datetime
import os
import sys

from . import weather, icons, render

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ICON_CACHE = os.path.join(os.path.dirname(__file__), "assets", "icons")


def _load_config():
    try:
        from .config import config
        return config
    except ImportError:
        print("Missing inky_weather/config.py — copy config.example.py and fill it in.",
              file=sys.stderr)
        raise


def _gather(use_fixture, cfg):
    if use_fixture:
        return weather.load_from_fixtures(FIXTURE_DIR)
    return weather.fetch_live(cfg["lat"], cfg["long"], cfg["google_weather_key"])


def _icons_for(items, size):
    return [icons.get_icon(item["icon_uri"], size, ICON_CACHE) for item in items]


def build_image(use_fixture, cfg):
    hours, days = _gather(use_fixture, cfg)
    hour_icons = _icons_for(hours, 34)
    day_icons = _icons_for(days, 26)
    now = datetime.datetime.now()
    return render.render_display(
        hours, days, hour_icons, day_icons,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M %p"),
    )


def push_to_display(img):
    """Send an image to the Inky Impression. Imported lazily (Pi-only dep)."""
    from inky.auto import auto
    display = auto()
    display.set_image(img.convert("RGB"))
    display.show()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inky weather display")
    parser.add_argument("--fixture", action="store_true",
                        help="Use bundled fixtures instead of the live API")
    parser.add_argument("--out", metavar="PATH",
                        help="Write PNG to PATH instead of the display")
    args = parser.parse_args(argv)

    cfg = {} if args.fixture else _load_config()
    if args.fixture and not cfg:
        cfg = {"location_name": "Blacksburg, VA"}

    try:
        img = build_image(args.fixture, cfg)
    except Exception as exc:  # render an error card rather than crash silently
        img = render.render_error(str(exc)[:80])

    if args.out:
        img.save(args.out)
        print("Wrote", args.out)
    else:
        push_to_display(img)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Render the fixtures to a PNG (offline, no Pi needed)**

Run:
```bash
python3 -m inky_weather.main --fixture --out fixture.out.png
```
Expected: `Wrote fixture.out.png` and an 800×480 PNG exists.

- [ ] **Step 3: Verify the output dimensions**

Run:
```bash
python3 -c "from PIL import Image; print(Image.open('fixture.out.png').size)"
```
Expected: `(800, 480)`

- [ ] **Step 4: Visually review**

Open `fixture.out.png`. Confirm against the design: 12 hourly columns on the left (temp icons, FL row, precip bars, UV row, hour labels), and the 10-day strip on the right with temp spread bars and stacked D/N precip bars + pips. Note: with `--fixture` and no `config.py`, icons still download from Google (network) — if fully offline, icons will be blank placeholders, which is expected.

- [ ] **Step 5: Commit**

```bash
git add inky_weather/main.py
git commit -m "feat: add main orchestration with fixture and PNG output modes"
```

---

### Task 21: Deployment docs

**Files:**
- Create: `README-inky.md`

- [ ] **Step 1: Write the deployment README**

Create `README-inky.md`:

```markdown
# Inky Impression Weather Display

Raspberry Pi + Pimoroni Inky Impression 7.3" weather display. Fetches Google
Maps Platform Weather forecasts and renders a 12-hour hourly panel plus a
10-day strip. Refreshes hourly via cron.

## Hardware
- Raspberry Pi (Pi 4 for dev, Pi Zero 2W recommended for the final install — needs a pre-soldered header)
- Pimoroni Inky Impression 7.3" (mounts on the 40-pin GPIO header)

## Setup (on the Pi)
1. Enable SPI and I2C: `sudo raspi-config` → Interface Options.
2. Clone the repo and create a virtualenv:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure:
   ```bash
   cp inky_weather/config.example.py inky_weather/config.py
   # edit config.py: google_weather_key, lat, long, location_name
   ```

## Test
- Offline render to PNG (no display needed):
  ```bash
  python3 -m inky_weather.main --fixture --out test.png
  ```
- Live fetch to the display:
  ```bash
  python3 -m inky_weather.main
  ```

## Schedule (hourly refresh)
Add to crontab (`crontab -e`), using the venv's Python:
```
0 * * * * cd /home/pi/magtag_weather_odin && /home/pi/magtag_weather_odin/.venv/bin/python -m inky_weather.main >> /home/pi/weather.log 2>&1
```

## Development (on a Mac)
```bash
pip install Pillow requests pytest
python3 -m pytest -v
python3 -m inky_weather.main --fixture --out fixture.out.png
```
The `inky` library is only needed on the Pi; it is imported lazily so tests and
`--out` rendering work without it.
```

- [ ] **Step 2: Commit**

```bash
git add README-inky.md
git commit -m "docs: add Inky deployment and development guide"
```

---

### Task 22: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `python3 -m pytest -v`
Expected: all tests pass (weather, icons, render, smoke).

- [ ] **Step 2: Regenerate the fixture PNG and review once more**

Run: `python3 -m inky_weather.main --fixture --out fixture.out.png`
Open it and confirm it matches the approved mockup layout.

- [ ] **Step 3: Final commit if anything changed**

```bash
git status
# if there are stray changes:
git add -A && git commit -m "chore: final verification pass"
```

---

## Self-Review Notes

- **Spec coverage:** platform/stack (Tasks 1, 20, 21) · config + location_name (19, 20) · header with location·date (15) · 12-hour rolling hourly panel with temp graph/feels/precip/UV/hours/night shading (16) · 10-day strip with shared-scale spread bars + stacked D/N horizontal precip bars + intensity pips (17, 18) · day/night precip split from API (8) · icon strategy via iconBaseUri (10) · °C→°F (3) · fixture mode + error card (19, 20) · pytest coverage of pure logic (3–9, 11–14) · cron deploy (21). All spec sections map to tasks.
- **Refinements over spec:** (1) icons sourced from Google `iconBaseUri` instead of a hand-redrawn sprite sheet; (2) semantic color constants with `COLOR_STORM=RED` so the display works on both the 7-color (2022) and 6-color (2024) Impression panels — the `inky` library auto-detects and quantizes.
- **Type consistency:** `HourForecast`/`DayForecast` dict keys are defined once in the header and used identically in Tasks 7–8 (producers) and 16–18 (consumers). `precip_kind` returns the same five names consumed by `kind_color`. `intensity_level` returns 0–3 consumed by the pip loop.
- **Open item for first live run (Task 20, live mode):** confirm the exact Weather API endpoint hostnames/paths and units param against current Google docs; only `weather.py` URL builders are affected, and the parse/render layers are already validated against fixtures.
