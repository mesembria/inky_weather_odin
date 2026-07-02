# Weather Display Redesign — Design Spec

**Date:** 2026-07-02
**Status:** Draft for review
**Supersedes:** the render layout from the initial Inky Impression port (weather.com-style
hourly panel + 10-day strip)

Reference mockups (real 800×480 renders in the 7-color palette):
`docs/design/redesign-mock-storm.png`, `docs/design/redesign-mock-hot.png`.

## 1. Purpose

The display sits beside a physical weather station, so **current conditions are
redundant**. Its job is **predictive decision support**: help decide how to prepare for
the next ~12 hours — what to wear, whether outdoor activity will be affected, and (in the
evening) whether the night brings storms, snow, or a comfortable open-window low.

Two audiences in one person: someone wanting a quick actionable verdict, *and* a data geek
who wants to see the underlying probabilities. The design serves both by pairing **advice
cards** (the verdict) with a **rich ensemble graph** (the evidence).

## 2. Design Principles

- **Advice first, data underneath.** Lead with plain-language verdicts; make the numbers
  available but subordinate.
- **Forward-looking.** Nothing about "right now." Everything is the next 12 hours.
- **Adaptive.** The display changes what it emphasizes based on the hour of day and what the
  forecast actually contains (storms, heat, snow, calm).
- **Show uncertainty, don't hide it.** Probabilities are rendered as spread, not just a
  single number.
- **Designed, not templated.** Editorial typography (condensed display face), a restrained
  use of the panel's fixed accent colors, generous whitespace — deliberately unlike the
  weather.com clone it replaces.
- **Legible on e-ink.** 800×480, ~7 fixed colors (black, white, red, green, blue, yellow,
  orange). Flat fills, high contrast, no reliance on fine gradients.

## 3. Data Sources

| Source | Role |
|---|---|
| **Google Maps Platform Weather API** (existing) | Deterministic hourly forecast: temp, feels-like, precip probability & type, thunderstorm probability, UV, condition + **official condition icons** (`iconBaseUri`). Drives the "expected" line, the advice logic, and the per-hour icons. |
| **Open-Meteo Ensemble API** (new) | GEFS ensemble members (hourly, free for non-commercial use, no API key). Drives the **temperature spread band** and the **precip spread**, plus the **confidence badge**. Endpoint: `https://api.open-meteo.com/v1/ensemble` with `models=gfs_seamless`, `hourly=temperature_2m,precipitation_probability` (or `precipitation`). |

Google's public API is powered by an ensemble model (WeatherNext 2) but only exposes
deterministic values + a probability — not raw members — hence the second source for spread.

The two sources are fetched independently; if Open-Meteo fails, the graph degrades gracefully
to the deterministic line with no band (the display must never crash on a partial fetch).

## 4. Layout ("Layout B")

800×480, top to bottom:

1. **Header band (~40px).** Location (condensed caps) + date on the left. On the right: a
   **confidence badge** (`◆ HIGH CONFIDENCE` / `◈ MIXED` / `◇ LOW AGREEMENT`, colored) over
   a small `updated · NEXT 12H` line. A 2px rule under the header.
2. **Advice banner (~132px).** Three equal cards side by side, separated by thin rules.
   Each card is **typographic, no icon**: a colored category label (e.g. `STORMS`), a large
   condensed verdict (`T-storms 2p`), and a small gray supporting detail (`65% · brief,
   heavy`). A 1px rule under the banner.
3. **Ensemble graph (remaining ~270px, full width).** See §6.

Rationale for Layout B over the sidebar variant (Layout A): the full-width graph gives the
ensemble bands room to read, which matters most for the data-geek half.

## 5. Advice Cards — the 3-slot adaptive system

**Model:** there is a *pool* of card types. Every refresh, each eligible card computes a
**priority score**; the top 3 fill the slots, rendered left→right in a stable display order.
This keeps the display relevant (morning shows dress/rain/UV; a stormy afternoon shows
storms/rain/dress; an evening shows overnight/etc.).

**Card pool** (all confirmed in scope):

| Card | Triggers when | Example verdict / detail |
|---|---|---|
| DRESS | always eligible (core) | `Warm, cools late` · `63–81° · humid AM` |
| RAIN / OUTDOORS | rain in window (core) | `Morning window` · `Dry till 12p · wet 12–4p` |
| STORMS | thunderstorm prob ≥ threshold | `T-storms 2p` · `65% · brief, heavy` |
| OVERNIGHT | evening refresh + night hours ahead | `Open tonight` · `Low 65° · clear & dry` |
| SNOW | snow in precip type/amount | `Snow after 12a` · `2–4"` |
| WIND | gusts over threshold | `Breezy` · `Gusts 25 mph pm` |
| SMOKE / AQI | AQI over threshold (wildfire season) | `Hazy` · `AQI 130 · limit exertion` |
| UV / SUN | UV index ≥ threshold, no bigger hazard | `Strong UV` · `Index 7 midday · hat + SPF` |
| SWING | ensemble spread wide | `Could be 78–88°` · `models disagree pm` |
| TREND | notable warmer/cooler vs today | `Cooler than today` · `−8° by evening` |

**Confidence** is a header badge, not a card (derived from mean ensemble band width).

**Vocabulary & thresholds are intentionally first-draft here** and will be worked through in
detail as the first implementation step (this is the "make or break" layer). Thresholds live
in `config.py` so wording/cutoffs can be tuned after living with the display. Priority scoring
(how a 65%-storm outranks a UV card, etc.) is part of that detailed pass.

WIND, SMOKE/AQI require fields not in the current Google parse; they come from Open-Meteo
(`wind_gusts_10m`) and Open-Meteo Air-Quality API respectively. If a field is unavailable, the
card is simply ineligible.

## 6. The Ensemble Graph

Full-width temperature graph with a precip strip along the bottom.

- **Temperature line.** The deterministic ("expected") value as a 3px black line with a dot
  and a condensed **°F label per hour**, colored by temperature (warm→red/orange,
  mild→ink, cool→blue).
- **Nested ensemble band.** Two stacked fills around the line: outer **p10–p90** (light) and
  inner **p25–p75** (darker). Widens with lead time and with convective uncertainty.
- **Temperature scale.** Faint horizontal **gridlines with °F labels** in a left gutter, so
  the band's magnitude is readable without per-hour band numbers.
- **Condition icons.** Google's official icon for **every hour**, in a row above the plot.
- **No explainer caption.** The `band = ensemble …` text in the mockups is an annotation for
  review only; the real render omits it (at most a small one-line legend, TBD).
- **Precip strip (bottom ~54px).** Per-hour rain chance with ensemble spread. **Two candidate
  styles, to be chosen during implementation on the real panel:**
  - *Floating box-plot* — light bar p10–p90, solid core p25–p75, median tick. Honest about the
    lower bound; can look odd floating off the baseline.
  - *Grounded + cap* — solid to median, faint cap to p90, grounded at 0. Intuitive; upside only.
  Storm hours color the bar red instead of blue. **The median % is labeled on every bar**
  (the number must stay readable — this was the whole point of the strip).
- **X axis.** AM/PM hour labels.

Known polish items for implementation: bottom gridline label can collide with the `RAIN %`
caption; near-zero precip bars shrink to specks (clamp a minimum).

## 7. Typography & Color

- **Display face:** a condensed grotesque (mockups use *DIN Condensed Bold*). DIN Condensed is
  a macOS system font and is **not** on the Raspberry Pi (DejaVu only), so we must **bundle an
  open-license condensed face** in `inky_weather/assets/fonts/` (e.g. Barlow Semi Condensed,
  Saira Condensed, or Oswald) and load it explicitly. Body/label text: a narrow sans (Arial
  Narrow in mockups → bundled equivalent).
- **Palette:** the existing 7-color constants. Accents used sparingly and semantically: red =
  hot/storm, orange = warm/caution, blue = cool/rain, green = good/comfortable, ink = neutral.
  Ensemble bands are light blue-grays that quantize acceptably on the panel.

## 8. Architecture / Modules

- `inky_weather/weather.py` — add an **Open-Meteo ensemble fetch + parse** (`fetch_ensemble`,
  returning per-hour member arrays or precomputed percentiles), aligned to the same 12-hour
  window as the Google hourly data. Keep pure/testable; keep the graceful-degradation contract.
- `inky_weather/advice.py` — **new module.** Pure functions: given parsed hours (+ ensemble +
  config thresholds) return the ordered list of ≤3 cards and the confidence badge. This is the
  isolated home for the "make or break" logic and is unit-tested independently of rendering.
- `inky_weather/render.py` — **rewrite** to the new layout: `draw_header` (with badge),
  `draw_advice_banner`, `draw_ensemble_graph`, and the composition in `render_display`. Drop
  the old hourly-panel/daily-strip code. Keep `render_error`.
- `inky_weather/config.py` / `config.example.py` — add Open-Meteo settings and the advice
  thresholds block.
- `inky_weather/icons.py` — reused as-is for Google icons; add a bundled-font loader helper if
  we don't put it in render.
- `inky_weather/main.py` — orchestrate the second fetch; pass ensemble data through.
- Fixtures — add an Open-Meteo ensemble fixture so `--fixture` renders the full design offline.

**Dropped from the old design (confirmed out of scope):** the feels-like row, the UV row as a
strip, and the entire 10-day right-hand forecast. Feels-like/UV survive only inside advice
logic; multi-day may return later as a TREND card but not as a strip.

## 9. Testing

- `advice.py`: unit tests over crafted hour sets asserting which cards win and their wording
  (storm day → STORMS present; hot dry evening → OVERNIGHT "open"; snowy night → SNOW).
- `weather.py`: ensemble parse tests over a fixture; percentile math.
- `render.py`: smoke test that `render_display` returns an 800×480 RGB image with both a
  full-data case and a **no-ensemble** (Open-Meteo-down) case.
- Manual: `--fixture --out` render, then an on-panel check that Google icons and the band
  colors dither legibly.

## 10. Open Items (resolved during implementation, not blocking this spec)

1. Advice vocabulary, thresholds, and priority scoring — detailed pass, config-driven.
2. Precip bar style (floating vs grounded) — chosen on the real panel.
3. Bundled condensed font choice + license.
4. Exact Open-Meteo request shape and whether to store raw members or precomputed percentiles.
