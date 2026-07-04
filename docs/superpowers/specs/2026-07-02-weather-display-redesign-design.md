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
| **Open-Meteo Ensemble API** (new) | GEFS ensemble members (hourly, free for non-commercial use, no API key). Drives the **temperature spread band** and the **precip spread**, plus the **confidence badge**. Endpoint: `https://api.open-meteo.com/v1/ensemble` with `models=gfs_seamless`, `hourly=temperature_2m,precipitation_probability` (or `precipitation`). Also supplies **`wind_gusts_10m`** for the WIND card and **`daily=sunrise,sunset`** for the DAYLIGHT card (same Open-Meteo request family). |
| **Open-Meteo Air-Quality API** (new) | US AQI for the SMOKE/AQI card (wildfire season). Endpoint: `https://air-quality-api.open-meteo.com/v1/air-quality` with `hourly=us_aqi`. **Confirmed worth the extra call.** |

Google's public API is powered by an ensemble model (WeatherNext 2) but only exposes
deterministic values + a probability — not raw members — hence the second source for spread.

The two sources are fetched independently; if Open-Meteo fails, the graph degrades gracefully
to the deterministic line with no band (the display must never crash on a partial fetch).

## 4. Layout ("Layout B")

800×480, top to bottom:

1. **Header band (~40px).** Location (condensed caps) + date on the left. On the right: a
   **confidence badge** (`◆ HIGH CONFIDENCE` / `◈ MIXED` / `◇ LOW AGREEMENT`, colored) over
   a small `updated · NEXT 12H` line. A 2px rule under the header.
2. **Advice banner (~104px).** Three equal cards side by side, separated by thin rules.
   Each card is **typographic, no icon**: a colored category label (e.g. `STORMS`) with the
   large condensed verdict (`T-storms 2p`) pulled up directly beneath it, and a small gray
   supporting detail (`65% · brief, heavy`) along the bottom. A 1px rule under the banner.
3. **Ensemble graph (remaining ~325px, full width).** See §6.

Rationale for Layout B over the sidebar variant (Layout A): the full-width graph gives the
ensemble bands room to read, which matters most for the data-geek half.

## 5. Advice Cards — the 3-slot adaptive system

**Model (validated against 7 scenarios):**

- **Slot 1 is always a temperature / "what to wear" card** (DRESS and its variants). It always
  carries the day's temp range, so the wear-decision is never crowded out.
- **Slots 2–3 are the top-scoring *situational* cards.** Each eligible situational card computes
  a **priority score**; the two highest fill the remaining slots, rendered left→right by score.

This kept the display relevant across every test: Phoenix → heat / UV / warm-night; Denver →
bundle-up / snow / wind; Seattle → cool-damp / daytime-rain / overnight; Sacramento → hot /
smoke / warm-night; Chicago → cool / gusty / turning-colder; plus the two original storm days.

**Slot 1 — temperature card.** A plain **state line keyed on the day's high** (like every other
band — no trend detection here; trends live in the TREND card). Detail is `{lo}–{hi}° · <cue>`,
with `· frost AM` appended when the low ≤ 32°, and `Warm`→`Warm & muggy` / `Cool`→`Cool & damp`
when humid / wet.

| Condition (high) | Verdict | Detail |
|---|---|---|
| ≥ 100° | `Dangerous heat` | `90–112° · hydrate, shade` |
| ≥ 90° | `Hot` | `80–98° · UV n, shade` |
| ≥ 80° | `Warm` / `Warm & muggy` | `63–81° · pleasant` / `· humid` |
| ≥ 62° | `Mild` | `52–66° · easy layers` |
| ≥ 48° | `Cool` / `Cool & damp` | `47–54° · layers` |
| ≥ 33° | `Cold` | `31–46° · coat · frost AM` |
| < 33° (freezing all day) | `Frigid` | `20–30° · bundle up` |

The 33–47° range — previously mislabeled `Cool` — now gets its own **`Cold`** band. `· frost AM`
is appended in the **Cold** band when the low ≤ 32° (as in the example above); **Frigid** omits
it because `bundle up` already subsumes the sub-freezing morning.

**Slots 2–3 — situational cards (first-draft triggers & scores; higher wins).**

**Framing is day/night aware** — a card only phrases for what you'd actually *do* about it. So
**daytime precip is its own outdoor-framed card**, and **anything that happens overnight (rain,
storms, snow, or just comfort) rolls up into a single sleep/windows-framed OVERNIGHT card** —
no "umbrella" advice for rain that falls while you're asleep, no "get outside" at 11pm.

*Daytime-framed cards (relevant hours are daytime):*

| Card | Trigger (daytime hours) | Score | Verdict / detail |
|---|---|---|---|
| ICE | precip = freezing rain / sleet (`precip_kind == "mix"`), pop ≥ 30 | 97 | `Ice 9a–12p` · `Icy roads · avoid driving` |
| SNOW | precip = snow, pop ≥ 30 | 95 | `Snow all day` · `6" likely · roads slick` |
| STORMS | thunder ≥ 45 / 25 | 90 / 68 | `T-storms 2p` · `65% · brief, heavy` |
| SMOKE | US AQI ≥ 150 / 100 | 88 / 64 | `Unhealthy air` · `AQI 168 · stay indoors` |
| WIND | gusts ≥ 35 / 25 | 80 / 56 | `Gusty` · `Gusts 45 mph · secure loose items` |
| RAIN | pop ≥ 50 (non-snow) | 72 | `Rain 8a–12p` · `70% · umbrella` (timing is the verdict) |
| UV | UV ≥ 9 / 6 | 60 / 44 | `Extreme UV` · `Index 11 · cover up` |
| TREND | a big swing **either direction**, ≥ 18° over the window | 58 | `Cooling off` · `58°→39° by 1a`  /  `Warming up` · `44°→78° by 5p` |

*OVERNIGHT (one card; fires when night hours are in the window; verdict = the most salient
overnight thing, precip before comfort). A precip branch is suppressed if the same precip
already has a daytime card, so a day-long snow doesn't also print "Snow overnight":*

| Sub-condition | Score | Verdict / detail |
|---|---|---|
| overnight ice | 88 | `Ice overnight` · `Low 30° · icy roads AM` |
| overnight thunder ≥ 30 | 85 | `Storms overnight` · `Low 66° · windows shut` |
| overnight snow | 82 | `Snow overnight` · `Low 30° · roads slick AM` |
| overnight rain ≥ 50 | 60 | `Rain overnight` · `Low 58° · windows shut` |
| low ≤ 45 | 55 | `Cold night` · `Low 28° · heat on` |
| low ≥ 70 | 50 | `Warm night` · `Low 74° · stuffy, fan on` |
| low 46–68 | 50 | `Windows open` · `Low 62° · comfortable` |
| low 69 | 50 | `Mild night` · `Low 69°` |

*Info tier (low priority; fills spare slots **below every hazard**, so the display almost always
shows three real cards without manufacturing filler):*

| Card | Trigger | Score | Verdict / detail |
|---|---|---|---|
| SWING | ensemble genuinely diverges (widest hour p10–p90 > ~15°) | 40 | `Could be 78–88°` · `models split by 4p` |
| MOON | full / near-full (illumination ≥ 90%) **and** a night is in the window | 36 | `Full moon` · `100% lit · bright night` |
| calm nudge | nothing hazardous is active (nothing scored ≥ 50) | 34 | `Get outside` (day) / `Quiet night` (night) · `Clear & calm` |
| DAYLIGHT | always available | 32 | `Sunset 8:31p` (day) / `Sunrise 6:12a` (night) · `plan outdoor time` |

MOON is computed from the date (a moon-phase calc), no API. DAYLIGHT uses Open-Meteo's daily
sunrise/sunset (so it fills even when the sun event is just past the 12-hour window). **If, after
the info tier, still fewer than two situational cards apply, the banner gracefully shows two
cards (wider) — no forced third.**

Notes from the workshop pass: TREND fires only on a genuinely big swing (≥ 18°, either
direction) and reports it factually (`Cooling off 105°→90°`), so it stays rare and never
editorializes a still-hot afternoon as "colder"; the old time-"window" metaphor (`Wet window`,
`Great window`, `Open tonight`) was dropped as confusing. **Confidence** is a header badge, not
a card (from mean band width) — distinct from the **SWING** info card, which puts a number on the
disagreement only when it's genuinely wide.

**Ties are broken by a fixed card-type precedence, high→low:** `ICE, SNOW, STORMS, SMOKE, WIND,
RAIN, UV, TREND`, then overnight precip, then overnight comfort, then the info tier
(`SWING, MOON, calm nudge, DAYLIGHT`). Within the same type, **daytime precedes overnight.** This
makes the two chosen cards deterministic for any input (e.g. a `UV` vs `overnight rain` tie at 60
resolves to `UV`, since `SUN` precedes `OVERNIGHT` in the list above; note daytime precip still
outranks UV because `OUTDOORS` precedes `SUN`).

These bands/scores/wording live in `config.py` so they can be tuned after living with the
display — this is the "make or break" layer and is expected to keep evolving. If a data field
is unavailable (e.g. Open-Meteo down), the dependent card is simply ineligible.

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
- **Precip strip (bottom ~82px).** Per-hour rain chance with ensemble spread. **Two candidate
  styles, to be chosen during implementation on the real panel:**
  - *Floating box-plot* — light bar p10–p90, solid core p25–p75, median tick. Honest about the
    lower bound; can look odd floating off the baseline.
  - *Grounded + cap* — solid to median, faint cap to p90, grounded at 0. Intuitive; upside only.
  Storm hours color the bar red instead of blue. **The median % is labeled on every bar**
  (the number must stay readable — this was the whole point of the strip).
- **X axis.** AM/PM hour labels.

Known polish items for implementation: bottom gridline label can collide with the `RAIN %`
caption; near-zero precip bars must draw nothing below ~5% pop (phantom-bar fix already proven
in the mockups). Snow precip bars are colored purple, storm bars red, rain bars blue.

## 7. Typography & Color

- **Display face: Oswald (SemiBold / weight 600), confirmed.** OFL-licensed, so we **bundle
  `Oswald` in `inky_weather/assets/fonts/`** and load it explicitly (the Raspberry Pi has only
  DejaVu). Used for the location header, card category labels, card verdicts, and the graph's
  temp numerals/gridline labels. Body/detail text stays a plain narrow sans (Arial Narrow in
  mockups → a bundled equivalent such as DejaVuSansCondensed on the Pi).
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

1. Advice vocabulary, thresholds, and priority scoring — **first draft in §5** (validated over 7
   scenarios); refined and moved into `config.py` during implementation.
2. Precip bar style (floating vs grounded) — chosen on the real panel.
3. ~~Bundled display font~~ — **resolved: Oswald (OFL).**
4. Exact Open-Meteo request shape and whether to store raw members or precomputed percentiles.
5. ~~SWING card scoring~~ — **resolved: low-priority info card (score 40), fires only on genuine
   divergence.** The **2-card gap** is also **resolved** via the info tier + graceful 2-card
   fallback (§5).

Sun times for the DAYLIGHT card come from the Open-Meteo daily endpoint
(`daily=sunrise,sunset`); MOON needs no API (moon-phase calc from the date).

## 11. Reference Mockups

Committed under `docs/design/` (real 800×480 renders in the 7-color palette, Oswald face):
`redesign-mock-storm.png`, `redesign-mock-hot.png`, the workshop set
`loc-phoenix/denver/seattle/sacramento/chicago.png`, and `demo-moon.png` (info-tier example).
