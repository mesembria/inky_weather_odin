# Precip segmented meter — design

**Date:** 2026-08-30
**Status:** Approved (pending spec review)
**Area:** `inky_weather/render.py` — the precip strip inside `draw_graph`

## Problem

The current precip representation draws a thin vertical bar per hour, its height
proportional to the exact probability of precipitation (`pop%`), with a small
`NN%` label above each bar and faint 50%/100% reference lines
(`render.py:170–191`).

From across the room this is hard to read. The exact percentage is noise — the
user does not care whether an hour is 30% or 35%. What they want to know is:

1. **How likely** — a coarse bucket: slim / moderate / definite chance.
2. **Compared to the other hours** — which part of the day is the wet part, at a
   glance, as a single shape.

The bar+number form fails both: numbers are unreadable at distance, and a
continuous height scale makes hour-to-hour comparison a squinting exercise.

## Goal

Replace the pop%-bars with a representation that is legible from a distance and
supports instant hour-to-hour comparison, quantized into **four** decision-
relevant buckets. Non-goals: exact percentages, sub-bucket precision, changing
anything else in the graph.

## Design: segmented meter

Each hour gets a **4-segment vertical meter**, grounded at the x-axis, filled
bottom-up according to the hour's tier. This is a deliberate merge of two forms
evaluated during brainstorming:

- **Heat strip** (a shaded band that darkens where rain builds) — gives the
  at-a-distance "where's the wet part" read. A fuller meter reads darker/taller.
- **Raindrop pips** (a countable stack) — gives per-hour precision. Count the
  filled segments to get the exact bucket.

The segmented meter unifies them: **coverage == count**. From afar the filled
portion forms the band; up close you count segments.

### Buckets and thresholds

`pop` is the hour's probability of precipitation (integer percent).

| Tier | Name | `pop` range | Segments filled |
|------|----------|-------------|-----------------|
| 0 | dry | `pop < 5` | 0 (draw nothing) |
| 1 | slight | `5 <= pop < 25` | 1 |
| 2 | chance | `25 <= pop < 55` | 2 |
| 3 | likely | `55 <= pop < 80` | 3 |
| 4 | definite | `pop >= 80` | 4 |

Thresholds `5 / 25 / 55 / 80` mirror National Weather Service vocabulary
(slight chance → chance → likely → definite). These live as a small ordered
threshold list / helper so they are easy to tune.

### Color

Filled segments use the **full kind palette**, via the existing classification
already computed in the loop:

```
kind = weather.precip_kind(pop, h["precip_type"], h["thunder"])
color = _KIND_BAR[kind]     # rain=BLUE, storm=RED, snow=PURPLE, mix=PURPLE
```

No new color constants. `_KIND_BAR` is reused as-is.

### Empty segments (unfilled headroom)

The `4 - tier` empty segments above the fill are drawn as a **faint outline** so
the meter reads as "N out of 4" and slight-vs-definite is a fill-level within a
consistent frame.

**Panel constraint (important):** the 6/7-color Inky quantizes color, and
near-white grays snap to white and vanish on hardware — the codebase already
documents this for gridlines (`render.py:33–35`) and solves it by drawing with
`INK` at low dot *coverage* (`_dotted_line`, `GRIDLINE_STEP`). Empty segment
outlines MUST use that same panel-safe faint technique (sparse `INK` dots /
dotted rectangle), **not** a near-white RGB gray such as `FAINT`.

Consequence, by surface:
- **Desktop PNG / preview:** the faint 4-slot frame is visible around every
  active meter.
- **Hardware:** the frame reads as a faint dotted ceiling if the coverage trick
  holds; in the worst case it degrades to clean grounded segmented bars where
  height alone encodes tier. Both remain legible and preserve the band read.

### Dry hours

Tier 0 (`pop < 5`) draws **nothing** — no empty box. This keeps mostly-dry days
clean and matches current behavior (today's loop does `continue` for
`pop < 5`). A dry hour is simply blank space in the band; the temp line and
axis continue through it as before.

### Wet gate and label

The existing gate is retained: `wet = any(h["pop"] >= 5 for h in hours)`.

- If **not** `wet`: draw no meters and no label (unchanged behavior — a fully
  dry day shows an empty band).
- If `wet`: draw the meters for tier >= 1 hours, and the strip label.

The label changes from `RAIN %` to **`RAIN`** (no numbers remain, so `%` is
misleading). Same position and font as today.

### Removed

- Per-bar `NN%` text labels.
- The 50% and 100% dotted reference lines (`render.py:175–178`) — there is no
  continuous scale left to reference against.

### Unchanged

Temperature line, points, and labels; the nested ensemble band; hourly icons;
temp gridlines; the x-axis and hour labels; the overall band footprint and the
`draw_graph` signature.

## Layout / geometry

The meter occupies the same lower band the bars use today, grounded at
`axis_y`, within the `bandh` (82px) region.

- Baseline: `pbase = axis_y` (grounded, as today).
- Meter height: reuse the current usable height `sc = bandh - 14` so a full
  (definite) meter reaches the same ceiling the old 100% bar did.
- 4 segments split `sc` evenly with a small inter-segment gap (≈3px). Segment
  height = `(sc - gap*3) / 4`.
- Segment width: centered on `xs[i]`, half-width clamped so meters never collide
  with neighbors (≈0.32 of the column, capped ~16px) and roughly matches the
  visual weight of today's bars.
- Segments drawn with small corner radius (≈2px) for a meter feel, filled or
  faint-outlined per the rules above.

Exact pixel constants are an implementation detail to tune against the live
render; the plan should verify visually.

## Implementation sketch

All changes are localized to the precip block of `draw_graph`
(`render.py:170–191`). No changes to `weather.py`, data flow, or callers.

1. Add a tier helper near the palette/precip constants:

   ```python
   _PRECIP_TIERS = (5, 25, 55, 80)   # lower bounds for slight/chance/likely/definite

   def _precip_tier(pop):
       """0=dry, 1=slight, 2=chance, 3=likely, 4=definite."""
       return sum(pop >= t for t in _PRECIP_TIERS)
   ```

2. Add a segment-drawing helper (or inline) that, given the hour's center `x`,
   the grounded baseline, `sc`, the tier, and the kind color, draws the filled
   segments solid and the empty segments as panel-safe faint dotted outlines.

3. Rewrite the precip block:
   - Keep the `wet` gate; drop the reference-line loop.
   - For each hour: compute `tier`; if `tier == 0`, skip. Else compute
     `kind`/`color` and draw the segmented meter.
   - Change the label text to `RAIN`.

## Testing

Existing tests live under `tests/`. Follow the current render-test pattern.

- **Tier boundaries:** `_precip_tier` returns the right bucket at and around each
  threshold: 4→0, 5→1, 24→1, 25→2, 54→2, 55→3, 79→3, 80→4, 100→4.
- **Dry gate:** an all-dry hour set (all `pop < 5`) draws no precip marks and no
  label — assert via the existing render/spy approach used for the current bars.
- **Wet render:** a mixed set produces the expected number of filled segments per
  hour (count filled vs faint), and uses the kind color from
  `weather.precip_kind`.
- **Regression:** temp line, ensemble band, icons, and axis are unaffected —
  cover with a golden/structural check consistent with existing render tests.

## Risks and mitigations

- **Faint frame vanishing on hardware.** Mitigated by using the coverage/dotted
  `INK` technique, not a near-white gray. If the frame is still too weak on the
  panel, the fallback (filled-only grounded segmented bars) is already legible;
  height encodes tier without the frame.
- **Threshold jitter at bucket edges.** An hour hovering at a boundary can flip
  buckets between refreshes. Accepted: only 4 boundaries, and the user
  explicitly does not care about sub-bucket precision. Thresholds are centralized
  for easy tuning.
- **Visual crowding at narrow column widths.** Mitigated by clamping segment
  half-width and verifying against the live 12-hour render.

## Out of scope

- Any redesign of the temperature graph, banner, or header.
- Showing intensity (QPF/accumulation) — this strip encodes probability only, as
  today.
- A visible on-screen legend for the tiers (the meter is intended to be
  self-evident; no legend exists for the current bars either).
