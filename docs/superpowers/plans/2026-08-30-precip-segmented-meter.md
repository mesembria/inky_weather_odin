# Precip Segmented Meter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the exact-percentage precip bars with a 4-bucket segmented meter that reads from a distance and supports instant hour-to-hour comparison.

**Architecture:** All changes are localized to the precip block of `draw_graph` in `inky_weather/render.py`. Add two module-level helpers (a tier classifier and a meter drawer) plus a panel-safe faint-rectangle helper, then rewrite the precip block to call them. No changes to `weather.py`, data flow, or any caller.

**Tech Stack:** Python 3, Pillow (PIL), pytest. Project virtualenv at `.venv/`.

## Global Constraints

- **Buckets (verbatim):** dry `pop < 5`; slight `5 <= pop < 25` → 1 segment; chance `25 <= pop < 55` → 2 segments; likely `55 <= pop < 80` → 3 segments; definite `pop >= 80` → 4 segments.
- **Panel-safe faint only:** empty segment outlines must be drawn with `INK` at low dot coverage (like `_dotted_line`/`GRIDLINE`), never a near-white gray such as `FAINT` — near-white grays snap to white and vanish on the 6-color panel.
- **Kind color from existing mapping:** filled segments use `_KIND_BAR[weather.precip_kind(pop, precip_type, thunder)]` (rain=`BLUE`, storm=`RED`, snow/mix=`PURPLE`). No new color constants.
- **Dry hours draw nothing.** Retain the existing wet gate: `wet = any(h["pop"] >= 5 for h in hours)`; if not wet, draw no meters and no label.
- **Label text is `RAIN`** (no `%`). No `NN%` per-bar text. No 50%/100% reference lines.
- **Run tests with the project venv:** `.venv/bin/python -m pytest ...`.
- Everything else in `draw_graph` (temp line, ensemble band, icons, temp gridlines, axis, hour labels) is unchanged.

---

### Task 1: Tier classifier `_precip_tier`

**Files:**
- Modify: `inky_weather/render.py` (add near the `_KIND_BAR` definition, ~line 90)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_PRECIP_TIERS = (5, 25, 55, 80)` and `_precip_tier(pop) -> int` returning `0` (dry) through `4` (definite).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
import pytest


@pytest.mark.parametrize("pop,tier", [
    (0, 0), (4, 0),        # dry
    (5, 1), (24, 1),       # slight
    (25, 2), (54, 2),      # chance
    (55, 3), (79, 3),      # likely
    (80, 4), (100, 4),     # definite
])
def test_precip_tier_boundaries(pop, tier):
    assert render._precip_tier(pop) == tier
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_precip_tier_boundaries -v`
Expected: FAIL with `AttributeError: module 'inky_weather.render' has no attribute '_precip_tier'`

- [ ] **Step 3: Write minimal implementation**

In `inky_weather/render.py`, immediately after the `_KIND_BAR = {...}` line (~line 90):

```python
# Precip probability buckets (lower bound of each non-dry tier), NWS-style:
# dry <5, slight 5-24, chance 25-54, likely 55-79, definite 80+.
_PRECIP_TIERS = (5, 25, 55, 80)


def _precip_tier(pop):
    """Map pop% to a bucket: 0=dry, 1=slight, 2=chance, 3=likely, 4=definite."""
    return sum(pop >= t for t in _PRECIP_TIERS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_precip_tier_boundaries -v`
Expected: PASS (10 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add 4-bucket precip tier classifier"
```

---

### Task 2: Meter drawing helpers `_faint_rect` and `_draw_precip_meter`

**Files:**
- Modify: `inky_weather/render.py` (add after `_precip_tier`)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `_precip_tier` is not needed here; the tier is passed in. Uses module constants `INK`, `GRIDLINE_STEP`.
- Produces:
  - `_faint_rect(d, x0, y0, x1, y1, step=GRIDLINE_STEP)` — stipples a rectangle perimeter with `INK` dots.
  - `_draw_precip_meter(d, cx, pbase, sc, half, tier, color)` — draws a grounded 4-segment meter centered at `cx`, baseline `pbase`, total height `sc`, segment half-width `half`; the bottom `tier` segments are filled solid `color`, the rest are faint outlines.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py`:

```python
def _meter_img():
    img = Image.new("RGB", (100, 120), render.WHITE)
    return img, ImageDraw.Draw(img)


def _count(img, color):
    return sum(1 for x in range(100) for y in range(120)
               if img.getpixel((x, y)) == color)


def test_precip_meter_fill_increases_with_tier():
    counts = []
    for t in (1, 2, 3, 4):
        img, d = _meter_img()
        render._draw_precip_meter(d, 50, 110, 80, 12, t, render.BLUE)
        counts.append(_count(img, render.BLUE))
    assert counts[0] < counts[1] < counts[2] < counts[3]


def test_precip_meter_uses_kind_color():
    img, d = _meter_img()
    render._draw_precip_meter(d, 50, 110, 80, 12, 1, render.RED)
    assert _count(img, render.RED) > 0
    assert _count(img, render.BLUE) == 0


def test_precip_meter_is_grounded_at_baseline():
    # Baseline is pbase=110; nothing should be filled below it.
    img, d = _meter_img()
    render._draw_precip_meter(d, 50, 110, 80, 12, 4, render.BLUE)
    assert all(img.getpixel((x, y)) == render.WHITE
               for x in range(100) for y in range(112, 120))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -k precip_meter -v`
Expected: FAIL with `AttributeError: module 'inky_weather.render' has no attribute '_draw_precip_meter'`

- [ ] **Step 3: Write minimal implementation**

In `inky_weather/render.py`, directly after `_precip_tier`:

```python
def _faint_rect(d, x0, y0, x1, y1, step=GRIDLINE_STEP):
    """Panel-safe faint rectangle outline: stipple the perimeter with INK dots.

    A near-white gray would snap to white and vanish on the 6-color panel, so
    'faint' comes from dot coverage instead — the same trick the gridlines use.
    """
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    for x in range(x0, x1 + 1, step):
        d.point((x, y0), fill=INK)
        d.point((x, y1), fill=INK)
    for y in range(y0, y1 + 1, step):
        d.point((x0, y), fill=INK)
        d.point((x1, y), fill=INK)


def _draw_precip_meter(d, cx, pbase, sc, half, tier, color):
    """Grounded 4-segment precip meter centered at cx.

    The bottom `tier` segments (0-4) are filled solid in `color`; the remaining
    segments are drawn as faint outlines so the meter reads as "N out of 4".
    """
    seg_n = 4
    gap = 3
    seg_h = (sc - gap * (seg_n - 1)) / seg_n
    for s in range(seg_n):
        sb = pbase - s * (seg_h + gap)
        st = sb - seg_h
        box = [cx - half, st, cx + half, sb]
        if s < tier:
            d.rounded_rectangle(box, radius=2, fill=color)
        else:
            _faint_rect(d, cx - half, st, cx + half, sb)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py -k precip_meter -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: add grounded segmented precip meter drawing helper"
```

---

### Task 3: Wire the meter into `draw_graph`

**Files:**
- Modify: `inky_weather/render.py:170-191` (the precip strip block inside `draw_graph`)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `_precip_tier`, `_draw_precip_meter`, `weather.precip_kind`, `_KIND_BAR`, and the locals already present in `draw_graph` (`xs`, `n`, `gw`, `gx`, `axis_y`, `bandh`).
- Produces: no new public interface; `draw_graph`'s signature is unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py`:

```python
def _graph_hours(pop, thunder=0, ptype="RAIN"):
    return [{"hour": (10 + i), "ampm_label": "{}p".format(i or 12),
             "is_daytime": True, "condition": "CLEAR", "icon_uri": "",
             "temp_f": 70 + i, "feels_f": 70 + i, "pop": pop,
             "precip_type": ptype, "thunder": thunder, "uv": 3}
            for i in range(12)]


def _band_color_count(hours, colors):
    """Count precip-colored pixels in the grounded meter band of a full graph."""
    img = Image.new("RGB", (render.WIDTH, render.HEIGHT), render.WHITE)
    d = ImageDraw.Draw(img)
    render.draw_graph(img, d, hours, [], [None] * 12, 14, 160,
                      render.WIDTH - 28, 300)
    axis_y = 160 + 300 - 16          # matches draw_graph's axis_y for these args
    return sum(1 for x in range(14, render.WIDTH - 14)
               for y in range(axis_y - 70, axis_y - 2)
               if img.getpixel((x, y)) in colors)


def test_precip_meter_absent_when_dry():
    # All hours below the dry threshold -> no meter pixels, whatever the color.
    count = _band_color_count(_graph_hours(0),
                              (render.BLUE, render.RED, render.PURPLE))
    assert count == 0


def test_precip_meter_present_when_wet():
    count = _band_color_count(_graph_hours(90), (render.BLUE,))
    assert count > 0


def test_precip_meter_uses_storm_color():
    # thunder >= 30 classifies as storm -> RED fill.
    hours = _graph_hours(90, thunder=50)
    assert _band_color_count(hours, (render.RED,)) > 0
    assert _band_color_count(hours, (render.BLUE,)) == 0


def test_precip_buckets_are_quantized():
    # 30% and 50% are both 'chance' -> identical meter; 90% ('definite') differs.
    blue = (render.BLUE,)
    assert _band_color_count(_graph_hours(30), blue) == \
           _band_color_count(_graph_hours(50), blue)
    assert _band_color_count(_graph_hours(30), blue) != \
           _band_color_count(_graph_hours(90), blue)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -k "precip_meter_absent or precip_meter_present or storm_color or buckets_are_quantized" -v`
Expected: FAIL — the current code draws continuous-height bars, so `test_precip_buckets_are_quantized` fails (30% and 50% produce different bar heights) and the storm/quantization assertions do not hold.

- [ ] **Step 3: Replace the precip block**

In `inky_weather/render.py`, replace the existing precip strip block (currently `render.py:170-191`, from the `# precip strip ...` comment through the `if wet: _ctext(... "RAIN %" ...)` line) with:

```python
    # precip strip (grounded 4-bucket meter, colored by kind)
    pbase = axis_y
    sc = bandh - 14
    wet = any(h["pop"] >= 5 for h in hours)
    if wet:
        half = min((gw - 32) / n * 0.32, 16)
        for i, h in enumerate(hours):
            t = _precip_tier(h["pop"])
            if t == 0:
                continue
            kind = weather.precip_kind(h["pop"], h["precip_type"], h["thunder"])
            col = _KIND_BAR.get(kind, BLUE)
            _draw_precip_meter(draw, xs[i], pbase, sc, half, t, col)
        _ctext(draw, "RAIN", gx + 2, pbase - bandh + 2, display_font(10, 600),
               INK, anchor="lm")
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py -k "precip_meter_absent or precip_meter_present or storm_color or buckets_are_quantized" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full render suite to check for regressions**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: PASS (all tests, including the pre-existing `test_draw_graph_runs_with_and_without_band` and `test_render_display_*`)

- [ ] **Step 6: Commit**

```bash
git add inky_weather/render.py tests/test_render.py
git commit -m "feat: replace precip bars with 4-bucket segmented meter"
```

---

### Task 4: Visual verification against the live render

**Files:**
- None modified (verification only).

**Interfaces:**
- Consumes: the full pipeline via the project's normal render path / fixtures.

- [ ] **Step 1: Render a sample display to an image**

Use the existing fixture-driven render path to produce a full 800x480 PNG (the same mechanism that produced `redesign_live.png`). If the repo has a script or test hook for this, use it; otherwise render `render.render_display(...)` with the hourly fixture data in `inky_weather/fixtures/hourly_response.json` and save to a scratch PNG.

Run (example):
```bash
.venv/bin/python -c "
from inky_weather import render, weather
# build hours from fixtures via the project's normal parsing path, then:
# img = render.render_display(hours, bands, icons, cards, badge, loc, date, upd)
# img.save('/tmp/precip_check.png')
print('rendered')
"
```

- [ ] **Step 2: Inspect the image**

Confirm by eye:
- Wet hours show grounded segmented meters; segment count matches the tier (slight=1 … definite=4).
- Dry hours are blank (no empty boxes).
- The label reads `RAIN` (no `%`), and there are no 50%/100% reference lines or per-bar numbers.
- Meters do not collide with neighbors at the 12-hour column width, and a definite meter reaches roughly the old 100%-bar ceiling.
- Storm hours (if present in the fixture) fill red; snow/mix fill purple; plain rain fills blue.

- [ ] **Step 3: Adjust constants only if needed**

If meters crowd or look too thin/tall, tune only `half` (the `0.32`/`16` clamp) and the `gap` inside `_draw_precip_meter`. Re-run `.venv/bin/python -m pytest tests/test_render.py -v` after any change. Commit only if a change was made:

```bash
git add inky_weather/render.py
git commit -m "fix: tune precip meter width/spacing for live render"
```

---

## Self-Review

**Spec coverage:**
- Buckets/thresholds → Task 1 (`_precip_tier`, `_PRECIP_TIERS`) + boundary tests.
- Segmented meter form, filled + faint segments → Task 2 (`_draw_precip_meter`, `_faint_rect`).
- Full kind palette → Task 3 (uses `weather.precip_kind` + `_KIND_BAR`), asserted by `test_precip_meter_uses_storm_color`.
- Panel-safe faint outline (no near-white gray) → Task 2 `_faint_rect` uses `INK` dots at `GRIDLINE_STEP`.
- Dry hours draw nothing → Task 3 `if t == 0: continue`, asserted by `test_precip_meter_absent_when_dry`.
- Wet gate + `RAIN` label, drop `%` labels and reference lines → Task 3 rewrite, asserted by `test_precip_meter_present_when_wet`.
- "Don't care 30 vs 35" quantization → `test_precip_buckets_are_quantized`.
- Same footprint / grounded / unchanged graph → Task 3 keeps `pbase`, `sc`, `bandh`; Task 4 visual check; existing regression tests retained.

**Placeholder scan:** No TBD/TODO. Task 4 Step 1 leaves the exact fixture-parsing invocation open because it depends on the repo's existing render entry point; this is a verification task, not a code deliverable, and the surrounding steps state exactly what to confirm.

**Type consistency:** `_precip_tier(pop) -> int` used consistently; `_draw_precip_meter(d, cx, pbase, sc, half, tier, color)` signature matches all call sites (Task 2 tests and Task 3 integration); `_faint_rect` signature matches its single caller. Color constants `BLUE`/`RED`/`PURPLE` and `_KIND_BAR` all exist in `render.py`.
