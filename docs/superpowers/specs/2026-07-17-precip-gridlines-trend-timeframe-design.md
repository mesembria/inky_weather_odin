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

## Change 2 — Trend card timeframe in the detail line

In `advice.py::_trend_card`, keep the `"TREND"` category label and the verdict
words. Make the **detail** line state the today-vs-yesterday framing explicitly.

| Case | Current detail | New detail |
|------|----------------|------------|
| Warmer/cooler day | `high 78° (-7) · low 58° (-7)` | `today 78° · 7° cooler than yesterday` |
| Steady | `high 80° · ~ yesterday` | `today 80° · same as yesterday` |
| Warmest/coolest stretch | `high 70° · warmer around it` | `today 70° · coolest day this week` |
| Warmest stretch | `high 76° · cooler around it` | `today 76° · warmest day this week` |

Details:

- Day-over-day case uses the absolute value of `dhi` with the direction word
  ("warmer"/"cooler") already implied by the verdict: `today {hi}° · {abs(dhi)}°
  {warmer|cooler} than yesterday`.
- The **low-delta append** (`· low {lo}° ({+d})`) is **dropped** — "than
  yesterday" already carries the framing, and the card is width-constrained
  (~253px at font 14).
- Steady case: `today {hi}° · same as yesterday`.
- Peak/dip (stretch) case: `today {hi}° · coolest day this week` (coolest stretch)
  / `today {hi}° · warmest day this week` (warmest stretch). "This week" is the
  right frame since the comparison is against the surrounding persisted +
  forecast days.

## Testing

- `tests/test_advice.py` asserts exact trend detail strings
  (e.g. `"high 78° (-7) · low 58° (-7)"`, `"high 80° · ~ yesterday"`,
  `"high 70° · warmer around it"`). Update every asserted trend detail to the new
  format. Verdict/accent/score assertions are unchanged.
- Add a render-level check that the precip gridlines appear only when the window
  has rain chance — e.g. a smoke test that `draw_graph` on an all-dry `hours`
  list draws no `"RAIN %"` caption / no strip gridlines, and a wet list does.
  (Keep it lightweight; the existing render smoke test in `tests/test_smoke.py`
  is the model.)

## Out of scope

- No change to bar color, width, `%` labels, temperature graph, or card scoring/
  precedence.
- No change to the OUTLOOK (forward multi-day) card.
