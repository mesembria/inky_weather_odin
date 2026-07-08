# Day-scale trend cards — design

**Date:** 2026-07-07
**Status:** Approved, ready for planning

## Problem

The current `TREND` card (`advice.py:132-144`) compares the first forecast hour to
the day's late high/low. Structurally this only captures the diurnal (night→day)
swing — "cooler at night, warmer during the day" — which is not useful in a climate
where that pattern is a given. A useful trend answers a **day-scale** question:
is today warmer or cooler than yesterday, and where does today sit relative to the
days around it?

## Goals

Replace the single intraday-swing card with day-scale trend signals:

1. **Day-over-day** — today's high vs *yesterday's* high, always shown (including
   the "same as yesterday" case, which is itself information).
2. **Window position** — is today the coolest/warmest day of a short straddling
   stretch. Shares the slot with day-over-day (either/or).
3. **Forward trend** — the direction of the next few days. Independent signal.

## Non-goals

- No new display layout. The banner remains exactly 3 card slots
  (`render.py:107`), slot 1 always DRESS.
- No local persistence / saved state. Past data comes from the API.
- Overnight-low framing stays owned by the existing `OVERNIGHT` card; trend cards
  headline on the daytime **high** (low only as a detail).

## Data sourcing

Backward-looking data comes from **Open-Meteo `past_days`**, not Google. Rationale:
Google's history endpoint (`history/hours:lookup`) returns only the last **24
hours** of hourly data — enough for a rough yesterday but not a clean calendar-day
high/low, and nothing for a multi-day window. Open-Meteo's daily endpoint returns
full calendar days for as many past days as requested, and the project already
talks to Open-Meteo for ensemble / dew-point / AQI.

- **`weather.py`** — new `fetch_past_daily(lat, long, ...)` (+ a fixture loader
  mirroring the existing `load_*_fixture` helpers) calling Open-Meteo's daily
  endpoint with `daily=temperature_2m_max,temperature_2m_min&past_days=3&forecast_days=1`.
  Returns highs/lows for `[t-3, t-2, t-1, today]` (today = the actual-so-far day).
- **`main.py`** — orchestrate the fetch with the same graceful-degradation pattern
  as ensemble/AQI/sun. If the past-data fetch fails or returns nothing, the
  backward `TREND` card cannot compute and is simply not emitted; the forward
  `OUTLOOK` card (Google-only) is unaffected.
- **Forward data** — the existing Google 10-day daily forecast (`days`, already
  fetched) supplies both the forward half of the window and the `OUTLOOK` card.

## Card logic

All thresholds below are defaults and tunable.

### Backward: always-on singular `TREND` card

One `TREND` card is generated per run (data permitting). Its default message is the
day-over-day comparison; when today is a genuine peak/dip of the straddling window,
the message upgrades to the window framing instead. This is how day-over-day and
window position stay mutually exclusive — same slot, one wins.

**Day-over-day (default message).** Compare today's forecast high to yesterday's
actual high (`yesterday` = `past[-2]` from the Open-Meteo array; `today` = `past[-1]`):

| Δhigh (today − yesterday) | Verdict | Detail | Accent |
|---|---|---|---|
| `≤ −10` | Much cooler | `high 60° (−12)` | blue |
| `−9 … −3` | Cooler day | `high 62° (−6)` | blue |
| `−2 … +2` | Steady | `high 68° · ~ yesterday` | gray |
| `+3 … +9` | Warmer day | `high 74° (+6)` | orange |
| `≥ +10` | Much warmer | `high 80° (+12)` | orange |

- Append `· low 51° (−4)` to the detail when `|Δlow| ≥ 5°`.

**Window upgrade (either/or).** Window = 3 past highs + today + 3 forward highs
(7 highs; forward half from the Google `days` forecast). When today's high is the
strict min or max of the window by `≥ 3°` over its nearest neighbor, replace the
message:

- min → **"Coolest stretch"** · `high 62° · warmer around it` (blue)
- max → **"Warmest stretch"** · `high 88° · cooler around it` (orange)

**Score ≈ 65.** High enough to outrank minor info (overnight-mild, UV, moon,
daylight) and to survive alongside a single hazard, but genuine danger (ice 97,
storm 90, smoke 88, plus a second competing hazard) can bump it from the 2
competable slots. Effectively always present on ordinary days.

### Forward: independent `OUTLOOK` card

Uses the next 3 Google forecast highs. Fires when the net change over those days is
`≥ 8°` **and** the direction is consistent (monotone, or net change dominates any
reversal).

- warming → **"Warming trend"** · `→ 78° by Fri` (orange)
- cooling → **"Cooling trend"** · `→ 58° by Fri` (blue)

Informational score ~54. Independent — competes normally and may appear alongside
the backward `TREND` card.

### Precedence

Add the categories to `_PRECEDENCE` (`advice.py:75`) for equal-score tie-breaks.
`TREND` keeps its existing precedence slot; `OUTLOOK` is added among the
informational categories.

## Removed

The intraday-swing block (`advice.py:132-144`) is deleted outright.

## Testing (TDD)

- Unit tests per generator over synthetic high/low arrays:
  - day-over-day: fires with correct verdict/accent at each threshold boundary,
    including the flat "Steady" case and the low-detail append.
  - window upgrade: fires only when today is a strict peak/dip by the margin;
    day-over-day is used otherwise (either/or precedence).
  - `OUTLOOK`: direction detection, net-change threshold, no-fire on flat/noisy.
- An Open-Meteo past-data fixture wired into the existing offline end-to-end render
  test, plus a degradation case (missing past data → no backward `TREND`, render
  still succeeds).
