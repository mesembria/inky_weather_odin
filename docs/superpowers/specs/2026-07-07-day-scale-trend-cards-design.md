# Day-scale trend cards — design

**Date:** 2026-07-07
**Status:** Implemented. **Revised 2026-07-08** — backward data source changed from
Open-Meteo `past_days` to **persisted Google daily highs** after live testing showed
Open-Meteo disagrees with the Google-anchored display (see "Data sourcing"). Sections
below reflect the shipped design.

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
- Overnight-low framing stays owned by the existing `OVERNIGHT` card; trend cards
  headline on the daytime **high** (low only as a detail).

## Data sourcing

**All trend temperatures come from Google**, the deterministic source the rest of
the display trusts. This is the core constraint, learned from live testing: the
first cut sourced the backward data from **Open-Meteo `past_days`**, but Open-Meteo
runs mean-biased vs Google (the codebase already compensates for this in
`recenter_bands`, which re-anchors the Open-Meteo ensemble onto Google temps). The
result was a card that read "Steady · high 94°" while the same screen showed Google's
88° and the day-over-day delta tracked Open-Meteo's model instead of the trusted
forecast. Mixing sources in the delta is also unsafe — a systematic Google-vs-Open-
Meteo offset would skew every day's delta. So the trend compares **Google-to-Google**.

Google's forecast is forward-only (today + 9 days), so "yesterday" must be
remembered from a previous run:

- **`history.py`** (new) — persists each run's Google daily high/low to a small
  git-ignored JSON file (`load_history`, `record_day`, pruned to ~10 days), and
  assembles the card's inputs (`trend_input(days, history, date)`): today's Google
  high/low (`days[0]`), yesterday's persisted high/low (or `None` if not yet
  recorded), and the surrounding-stretch highs (up to 3 persisted past days + the
  next 3 Google forecast days, excluding today).
- **`main.py`** — loads history, builds the trend input, records today's Google
  high/low for tomorrow. History reads/writes are best-effort (`_safe` / swallowed
  write errors) so storage problems never break the render.
- **Consequence:** day-over-day needs one prior run to exist, so the card begins on
  **day two**; the window peak/dip engages as history accrues. This first-run gap is
  the accepted cost of staying bias-free and display-consistent.
- **Forward data** — the existing Google 10-day daily forecast (`days`) supplies the
  forward stretch highs and the `OUTLOOK` card.

## Card logic

All thresholds below are defaults and tunable.

### Backward: always-on singular `TREND` card

One `TREND` card is generated per run (data permitting). Its default message is the
day-over-day comparison; when today is a genuine peak/dip of the surrounding stretch,
the message upgrades to the window framing instead. This is how day-over-day and
window position stay mutually exclusive — same slot, one wins.

**Day-over-day (default message).** Compare today's Google forecast high to
yesterday's persisted Google high (`today` = `days[0]`; `yesterday` from
`history.py`). Needs a recorded yesterday, so it is silent on the first run:

| Δhigh (today − yesterday) | Verdict | Detail | Accent |
|---|---|---|---|
| `≤ −10` | Much cooler | `high 60° (−12)` | blue |
| `−9 … −3` | Cooler day | `high 62° (−6)` | blue |
| `−2 … +2` | Steady | `high 68° · ~ yesterday` | gray |
| `+3 … +9` | Warmer day | `high 74° (+6)` | orange |
| `≥ +10` | Much warmer | `high 80° (+12)` | orange |

- Append `· low 51° (−4)` to the detail when `|Δlow| ≥ 5°`.

**Window upgrade (either/or).** The surrounding stretch = up to 3 persisted past
highs + up to 3 forward Google-forecast highs (today excluded). The upgrade only
engages when the stretch has **≥ 4** days — so a pure-forecast run (forward-only,
before history builds) can't masquerade as a "stretch" that overlaps `OUTLOOK`.
When today's high is the strict min or max of the stretch by `≥ 3°`, replace the
message:

- min → **"Coolest stretch"** · `high 62° · warmer around it` (blue)
- max → **"Warmest stretch"** · `high 88° · cooler around it` (orange)

The upgrade can fire even before a "yesterday" is recorded, since it needs only the
stretch, not the day-over-day delta.

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

- Unit tests per generator over synthetic today/yesterday/stretch inputs:
  - day-over-day: fires with correct verdict/accent at each threshold boundary,
    including the flat "Steady" case, the low-detail append, and the first-run
    (no yesterday) → no card.
  - window upgrade: fires only when today is a strict peak/dip by the margin AND
    the stretch has ≥ 4 days; can fire without a yesterday; day-over-day is used
    otherwise (either/or precedence).
  - `OUTLOOK`: direction detection, net-change threshold, no-fire on flat/noisy.
- `history.py` tests: `load_history` on a missing file → `{}`; `record_day`
  round-trips and prunes to `keep`; write errors are swallowed; `trend_input`
  assembles today/yesterday/stretch and yields no yesterday when history is empty.
- Fixture end-to-end render still succeeds (fixture mode synthesizes a warmer
  "yesterday" so the demo shows a "Cooler day" card).
