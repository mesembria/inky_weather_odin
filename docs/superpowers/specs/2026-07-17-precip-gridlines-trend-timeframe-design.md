# Design: Precip-bar gridlines & trend-card timeframe

Date: 2026-07-17

Two small, independent display-readability changes to the Inky Impression weather
render.

## Motivation

1. **Precip bars have no visible max reference.** In `render.py::draw_graph` the
   rain-chance strip draws only colored bars (height ∝ `pop%`) plus a `%` label
   above each. Nothing marks the 0–100% ceiling, so a single short bar gives no
   sense of how close to certain the rain is.
2. **The TREND card doesn't state its timeframe.** `advice.py::_trend_card`
   compares *today* to *yesterday* (or flags today as the peak/dip of the
   surrounding days), but the card reads ambiguously as maybe-now / maybe-tomorrow.

## Change 1 — Precip strip reference gridlines

In `render.py::draw_graph`, add two faint horizontal reference lines across the
precip strip so each bar reads against a marked scale.

- **Levels:** 50% and 100% of the bar band. The 100% line sits at the top of the
  band (`y = pbase - sc`); the 50% line at its midpoint (`y = pbase - sc * 0.5`).
  The existing x-axis line is the 0% baseline.
- **Gate:** draw the gridlines *and* the existing `"RAIN %"` caption only when
  `any(h["pop"] >= 5 for h in hours)` — i.e. exactly when at least one precip bar
  is drawn (bars already skip `pop < 5`). On a bone-dry window the strip is
  completely clean: no lines, no caption.
- **Style:** same faint gray as the temperature gridlines, `(230, 231, 236)`,
  width 1, spanning the plot width (`lx` → `gx + gw`). Drawn **before** the bars
  and `%` labels so the colored fill and numbers render on top.
- **No numeric level markers** — lines only.

### Ordering within `draw_graph`

The precip section currently: loops bars, then draws the `"RAIN %"` caption. New
order:

1. Compute `wet = any(h["pop"] >= 5 for h in hours)`.
2. If `wet`: draw the two gridlines first, then the bar loop (unchanged), then the
   `"RAIN %"` caption.
3. If not `wet`: draw nothing in the strip (the bar loop is a no-op anyway since
   every bar is skipped; the caption is now suppressed).

## Change 2 — Trend card: explicit timeframe + late-day forward pivot

Keep the `"TREND"` category label and the verdict words. Two parts:

### 2a. Detail line states the timeframe explicitly

The **detail** line names which two days are being compared:

| Case | Current detail | New detail |
|------|----------------|------------|
| Warmer/cooler day (morning) | `high 78° (-7) · low 58° (-7)` | `today 78° · 7° cooler than yesterday` |
| Steady (morning) | `high 80° · ~ yesterday` | `today 80° · same as yesterday` |
| Coolest stretch | `high 70° · warmer around it` | `today 70° · coolest day this week` |
| Warmest stretch | `high 76° · cooler around it` | `today 76° · warmest day this week` |

- Day-over-day case uses `abs(dhi)` with the direction word ("warmer"/"cooler")
  already implied by the verdict: `{ref} {hi}° · {abs(dhi)}° {warmer|cooler} than
  {base}`.
- The **low-delta append** (`· low {lo}° ({+d})`) is **dropped** — the "than X"
  phrase already carries the framing, and the card is width-constrained (~253px
  at font 14).

### 2b. Pivot forward late in the day

By late afternoon today's high has already happened, so "today vs yesterday" is
stale. Pivot the **default day-over-day comparison** based on the current local
hour (`hours[0]["hour"]`, 0–23):

- **Before the cutoff (morning/midday):** compare **today vs yesterday** (needs
  persisted `yesterday`). Detail: `today {hi}° · {n}° warmer/cooler than
  yesterday` / `today {hi}° · same as yesterday`.
- **At/after the cutoff:** compare **tomorrow vs today** (needs `tomorrow` from
  the Google daily forecast, `days[1]`). Detail: `tomorrow {hi}° · {n}°
  warmer/cooler than today` / `tomorrow {hi}° · same as today`.

New constant `TREND_PIVOT_HOUR = 15` (3pm). Chosen so the pivot is active by 4pm
(the user's example) and today's high — typically 3–5pm — is essentially
realized. Adjustable knob; called out here for review.

- **Verdict words are unchanged** in both directions (Steady / Warmer day /
  Cooler day / Much warmer / Much cooler), keyed on `dhi`. The detail line is what
  carries the timeframe — consistent with the "timeframe in the detail line"
  decision. The forward detail's `tomorrow … than today` removes any ambiguity.
- **The peak/dip stretch upgrade is unchanged and stays all-day.** It flags today
  as a local extreme of the surrounding *past + forward* days ("this week"), which
  remains meaningful in the afternoon; only the day-over-day default pivots. The
  stretch check runs first, as today; the pivot applies only when it doesn't fire.
- **Returns `None`** (card omitted, slot goes to the next-best card) when the
  needed neighbor is missing: no `yesterday` before the cutoff, or no `tomorrow`
  after it.

### Data wiring

- `history.trend_input` adds a `"tomorrow"` key: `{"hi_f","lo_f"}` from `days[1]`
  when `len(days) >= 2`, else `None`. Existing `today`/`yesterday`/`stretch_his`
  unchanged.
- `main.build_image`'s **fixture** branch adds a synthetic `"tomorrow"` (from
  `days[1]`) so the offline preview still renders a trend card.
- `_trend_card` gains `tomorrow` and `now_hour` parameters. `build_cards` derives
  `now_hour = hours[0]["hour"]` and passes it through; no new argument to
  `build_cards` itself.
- Precedence vs OUTLOOK is unchanged: if both fire in the afternoon, TREND
  (nearer-term, higher score) still wins the slot. No scoring change.

## Testing

- `tests/test_advice.py` asserts exact trend detail strings
  (e.g. `"high 78° (-7) · low 58° (-7)"`, `"high 80° · ~ yesterday"`,
  `"high 70° · warmer around it"`). Update every asserted trend detail to the new
  format. Verdict/accent/score assertions are unchanged.
- The trend tests / `_hours` helper must set `hours[0]["hour"]` and the
  `_trend_card`/`_trend` helpers must supply `tomorrow` + `now_hour`. Existing
  day-over-day tests run with a **before-cutoff** hour (e.g. 9) so they still
  exercise the today-vs-yesterday branch.
- Add pivot tests: at/after `TREND_PIVOT_HOUR` the card compares tomorrow vs today
  (`"tomorrow …° · … than today"`); before it, today vs yesterday. Cover the
  boundary hour (`== TREND_PIVOT_HOUR` pivots) and the `None` cases (no
  `yesterday` before cutoff, no `tomorrow` after).
- Add a render-level check that the precip gridlines appear only when the window
  has rain chance — e.g. a smoke test that `draw_graph` on an all-dry `hours`
  list draws no `"RAIN %"` caption / no strip gridlines, and a wet list does.
  (Keep it lightweight; the existing render smoke test in `tests/test_smoke.py`
  is the model.)

## Out of scope

- No change to bar color, width, `%` labels, temperature graph, or card scoring/
  precedence.
- No change to the OUTLOOK (forward multi-day) card.
- The peak/dip stretch upgrade keeps its today-anchored behavior; it does not
  pivot forward.
