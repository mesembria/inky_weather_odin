# Resilient live fetch + stale-image fallback

**Date:** 2026-08-01
**Status:** Approved design

## Problem

When the hourly cron run can't reach the Google Weather API, `main.build_image()`
raises and `main.main()` (main.py:109-110) catches it and paints a full-screen
error card via `render.render_error()` — "Weather update failed" plus the raw
exception text (`str(exc)[:80]`). In practice the exception is a connection-level
failure from `requests`/`urllib3`:

```
HTTPSConnectionPool(host='weather.googleapis.com', port=443): Max retries exceeded ...
```

surfaced by the only unguarded fetch, `weather.fetch_live` (main.py:53). The four
supplementary fetches are already wrapped in `_safe()` and degrade silently.

Two problems: (1) a single transient Wi-Fi/DNS blip blanks the display for a whole
hour, and (2) the fallback is a large, alarming error screen rather than the
still-useful last-hour forecast.

## Goals

- Absorb transient connection failures with bounded retries before giving up.
- On total failure, keep the previous hour's forecast on screen with a small,
  unobtrusive staleness indicator — no giant error card.
- Preserve current behavior when there is genuinely nothing to show (first run,
  no cache).

## Non-goals

- Retrying the supplementary fetches (ensemble, air quality, sun, dew point).
  They already degrade gracefully via `_safe()`; adding backoff to each could add
  minutes to the job.
- Retrying HTTP status errors (4xx/5xx). A bad key or bad request won't fix
  itself; those fail fast.
- Changing the layout or content of the cached forecast on the stale render. We
  redisplay it verbatim plus a corner marker.

## Key technical fact

The Inky Impression is e-ink and retains its last image without a redraw. The
fallback therefore doesn't need to reconstruct the forecast — it re-pushes the
last-good rendered image (which we cache) with a stale marker stamped on top.

## Design

### 1. Retry on connection failures (`weather.py`)

Add an internal helper used only by the primary live fetch:

```python
def _get_with_retries(url, timeout, attempts=5, backoff=2.0, sleep=time.sleep):
    """GET url, retrying only on connection-level failures.

    Retries on requests.exceptions.ConnectionError and .Timeout (the
    "Max retries exceeded" case). Sleeps backoff * 2**n between attempts
    (2, 4, 8, 16s across 5 attempts). Re-raises the last exception when all
    attempts are exhausted. `sleep` is injectable so tests don't wait.
    """
```

- Both GETs in `fetch_live` (hourly + daily) route through `_get_with_retries`.
- Only `ConnectionError` and `Timeout` are retried. Any other exception (and the
  `WeatherAPIError` raised by `_raise_for_api_error` after a successful GET)
  propagates immediately — no retry.
- Defaults: `attempts=5`, `backoff=2.0` → sleeps of 2, 4, 8, 16s (worst case
  ~30s of waiting before falling back).

### 2. Cache the last-good render (`cache.py`, new module)

Mirrors `history.py`: file beside `__file__`, atomic `tmp` + `os.replace`,
best-effort with swallowed `OSError`.

```python
DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "last_display.png")

def save_display(img, path=DEFAULT_PATH):
    """Persist the last-good RGB render (pre-quantization). Best-effort."""

def load_display(path=DEFAULT_PATH):
    """Return the cached PIL Image, or None if missing/unreadable."""
```

`last_display.png` is a runtime artifact and belongs in `.gitignore`.

### 3. Stale pill (`render.py`)

```python
def stamp_stale(img):
    """Draw a small 'STALE' pill in the top-right corner; return the image."""
```

- Pure image operation: input image in, marked image out. No I/O.
- Uses existing constants (`RED` background, `WHITE` text, `display_font`).
- Placed in the top-right corner so it doesn't cover forecast content. The
  cached header already shows the original "updated 3:00pm" time, so the pill
  only signals *that* the data is old, not *when*.

### 4. Wiring (`main.py`)

- **Live success:** after `build_image()` returns, call `cache.save_display(img)`
  before pushing. Fixture runs (`--fixture`) do not save — they're fake data.
- **Failure:** in the existing `except Exception` block, before rendering the
  error card, attempt `cache.load_display()`:
  - Cache present → `img = render.stamp_stale(cached)`; continue to push/`--out`.
  - Cache absent (first run, or deleted) → `render.render_error(...)`, unchanged.
- Fixture runs never read the cache either, keeping previews isolated.

Resulting `main()` control flow:

```
try:
    cfg = fixture-cfg or _load_config()
    img = build_image(use_fixture, cfg)
    if not use_fixture:
        cache.save_display(img)          # best-effort
except Exception as exc:
    cached = None if use_fixture else cache.load_display()
    img = render.stamp_stale(cached) if cached else render.render_error(str(exc)[:80])
# then: --out save, or push_to_display(img)
```

## Testing

- **`_get_with_retries`**
  - Raises `ConnectionError` N−1 times then returns an OK response → returns that
    response; recorded `sleep` delays are `[2, 4, 8, 16][:N-1]`.
  - All attempts raise `ConnectionError` → re-raises after `attempts` tries.
  - A non-connection error (e.g. `ValueError`) is raised immediately, no retry,
    no sleep.
- **`cache`**
  - `save_display` then `load_display` round-trips an image through a tmp path.
  - `load_display` returns `None` for a missing/unreadable path.
- **`stamp_stale`**
  - Applied to a blank image: the top-right pill region gains `RED`/`WHITE`
    pixels; a sampled region outside the pill is unchanged.
- **Failure wiring (`main`)**
  - `fetch_live` monkeypatched to raise, cache present → pushed/out image carries
    the pill (assert via `stamp_stale` marker region).
  - `fetch_live` raises, no cache → error card path taken.

## Files touched

- `weather.py` — add `_get_with_retries`; route `fetch_live`'s two GETs through it.
- `cache.py` — new module: `save_display`, `load_display`.
- `render.py` — add `stamp_stale`.
- `main.py` — save cache on live success; stale-fallback in the `except` block.
- `.gitignore` — add `inky_weather/last_display.png`.
- `tests/` — new tests per the plan above.
