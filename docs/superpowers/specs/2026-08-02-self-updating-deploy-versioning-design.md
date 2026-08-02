# Self-updating deploy + versioning

**Date:** 2026-08-02
**Status:** Approved design

## Problem

The Pi runs the display hourly via cron, calling `python -m inky_weather.main`
directly (see README "Schedule"). When code is pushed to `origin/main`, nothing
on the Pi picks it up — a person must SSH in and `git pull`. There is also no way
to tell, from the device or the logs, which version of the code is running or
whether it is the latest.

Two wants:
1. Each hourly run should update the checkout from `origin/main` before running,
   so a push to main reaches the Pi automatically on the next run.
2. The running code should be versioned and that version visible, so it's obvious
   what's running and whether it's current.

## Goals

- On each run, bring the checkout to exactly match `origin/main` before launching
  the display code, in a way that guarantees the freshly-pulled code runs *this*
  cycle.
- Never let an update problem (offline, fetch failure) blank or block the display
  — fall back to running whatever is already checked out.
- Auto-reinstall Python dependencies when, and only when, `requirements.txt`
  changed in the update.
- Give the code a zero-maintenance version derived from git, surfaced both in the
  log and on the panel.

## Non-goals

- Rollback / health-checking of a bad update. If a pushed commit is broken, the
  existing error-card / stale-image fallback (from the resilience feature) already
  keeps the last-good forecast on screen; automatic rollback is out of scope.
- Updating from any branch other than `main`.
- A human-maintained semantic-version file. Versioning is git-derived; tagging is
  optional and, when done, is reflected automatically.
- Self-healing when `run.sh` itself changes mid-run (see Known caveat).

## Key technical facts

- You cannot reliably hot-reload changed code into an already-running Python
  process. The update must therefore happen in a separate step that completes
  *before* the display process starts. A wrapper script that updates and then
  launches Python satisfies this.
- `config.py`, `daily_history.json`, `last_display.png`, and `*.tmp` are all
  gitignored, so a `git reset --hard origin/main` cannot clobber configuration or
  runtime state. This makes hard reset safe as the update strategy.
- `git describe --tags --always --dirty` yields a useful version with no
  maintenance: the short commit SHA before any tags exist, and `v1.2.0` /
  `v1.2.0-3-gabc1234` once tags are present. A `-dirty` suffix flags a
  locally-modified checkout.

## Design

### 1. `run.sh` (new, repo root) — the wrapper cron invokes

Cron calls `run.sh` instead of Python directly. It updates the repo, optionally
reinstalls deps, logs a one-line summary, then `exec`s the display process.

- Path-independent: derives `REPO` from the script's own location
  (`dirname "${BASH_SOURCE[0]}"`) and `cd`s there.
- Overridable via environment variables so tests can substitute stubs:
  `INKY_PYTHON`, `INKY_PIP`, `INKY_RUN_CMD` (default `$PY -m inky_weather.main`),
  `INKY_REMOTE` (default `origin`), `INKY_BRANCH` (default `main`).
- `set -uo pipefail` but **not** `set -e`: the script must continue past a failed
  fetch so a network blip never stops the display from running current code.
- Update strategy: `git fetch --quiet $REMOTE $BRANCH` then
  `git reset --hard --quiet FETCH_HEAD`. `FETCH_HEAD` is used (rather than
  `origin/main`) so the reset targets exactly what was just fetched.
- Dependency handling: capture `git hash-object requirements.txt` before and after
  the update; if it changed, run `$PIP install -q -r requirements.txt` (log, and
  log a failure but do not abort).
- Logging: one line to stdout (cron already redirects `>> weather.log 2>&1`):
  - offline: `update: fetch failed (offline?), running current <ver>`
  - deps: `update: requirements.txt changed, reinstalling`
  - result: `update: weather <ver> (up to date)` or
    `update: weather <old> -> <new> (updated)`
- Ends with `exec $RUN_CMD` so the display process replaces the shell.

Reference implementation:

```bash
#!/usr/bin/env bash
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$REPO" || exit 1
PY="${INKY_PYTHON:-$REPO/.venv/bin/python}"
PIP="${INKY_PIP:-$REPO/.venv/bin/pip}"
RUN_CMD="${INKY_RUN_CMD:-$PY -m inky_weather.main}"
REMOTE="${INKY_REMOTE:-origin}"; BRANCH="${INKY_BRANCH:-main}"
ver(){ git describe --tags --always --dirty 2>/dev/null || echo unknown; }
log(){ echo "$(date '+%F %T') update: $*"; }

before=$(git rev-parse HEAD 2>/dev/null || echo none); before_ver=$(ver)
req_before=$(git hash-object requirements.txt 2>/dev/null || echo none)
if git fetch --quiet "$REMOTE" "$BRANCH" 2>/dev/null; then
  git reset --hard --quiet FETCH_HEAD
else
  log "fetch failed (offline?), running current $before_ver"
fi
after=$(git rev-parse HEAD 2>/dev/null || echo none); after_ver=$(ver)
req_after=$(git hash-object requirements.txt 2>/dev/null || echo none)
if [ "$req_before" != "$req_after" ]; then
  log "requirements.txt changed, reinstalling"
  $PIP install -q -r requirements.txt || log "pip install failed"
fi
if [ "$before" = "$after" ]; then
  log "weather $after_ver (up to date)"
else
  log "weather $before_ver -> $after_ver (updated)"
fi
exec $RUN_CMD
```

### 2. `inky_weather/version.py` (new)

```python
def get_version():
    """Return `git describe --tags --always --dirty` for the repo, or 'unknown'."""
```

- Runs `git -C <repo_root> describe --tags --always --dirty` via `subprocess.run`
  with `capture_output=True, text=True, timeout=5`.
- `repo_root` is `os.path.dirname(os.path.dirname(__file__))`.
- Returns the stripped stdout; returns `"unknown"` on empty output or any
  exception (missing git, not a checkout, timeout).

### 3. Show the version in the header (`render.py`, `main.py`)

- New pure helper in `render.py`:
  ```python
  def _updated_label(updated_str, version=None):
      base = updated_str + " · NEXT 12H"
      return base + " · " + version if version else base
  ```
- `draw_header(draw, location, date_str, updated_str, badge, version=None)` builds
  the updated-line text via `_updated_label` (replacing the current inline
  `updated_str + " · NEXT 12H"` at render.py:103). Right-anchored at `WIDTH-20`,
  font size 12 — unchanged except for the appended version.
- `render_display(..., version=None)` threads `version` through to `draw_header`.
- `main.build_image` obtains the version once via `version.get_version()` and
  passes it to `render_display`.
- The stale-fallback and error-card paths are untouched: a stale render reuses the
  cached image, whose header already carries the version that produced it (the
  correct thing to show); `render_error` gains no version (first-run/no-cache case,
  out of scope).

### 4. Testing

- **`version.get_version`** (`tests/test_version.py`, new):
  - `subprocess.run` mocked to return stdout `"v1.0.0\n"` → returns `"v1.0.0"`.
  - mocked to return empty stdout → returns `"unknown"`.
  - mocked to raise (e.g. `FileNotFoundError`) → returns `"unknown"`.
- **`_updated_label`** (`tests/test_render.py`):
  - with a version → string ends with `" · v1.0.0"`.
  - without a version (`None`) → string is just `"<updated> · NEXT 12H"`.
- **`run.sh`** (`tests/test_run_sh.py`, new — pytest driving `bash` via
  `subprocess`, using temp git repos and stubs; skip if `git`/`bash` unavailable):
  - New commit on the origin → running `run.sh` in the clone hard-resets the clone
    to origin's HEAD and invokes `INKY_RUN_CMD`; log says `updated`.
  - Already current → clone HEAD unchanged; log says `up to date`.
  - Unreachable remote (`INKY_REMOTE` set to a bad path) → clone unchanged, log
    says `fetch failed`, and `INKY_RUN_CMD` still runs.
  - Origin commit that changes `requirements.txt` → stub `INKY_PIP` is invoked and
    log says `reinstalling`.
  - `INKY_RUN_CMD` is exec'd last in every case (assert via a marker file it
    writes).

### 5. README

- New "Auto-update" subsection under Schedule explaining that `run.sh` updates from
  `origin/main` each run, reinstalls deps on `requirements.txt` changes, and runs
  current code when offline; note the hard-reset strategy and that gitignored
  config/state are safe.
- Change the crontab line from the direct Python invocation to:
  `0 * * * * /home/pi/inky_weather_odin/run.sh >> /home/pi/weather.log 2>&1`
- Document `chmod +x run.sh` and how the version works, including tagging a release
  (`git tag v1.0.0 && git push --tags`) so the panel/log show `v1.0.0`.

## Known caveat

If a push changes `run.sh` itself, bash may have already read the previous version
into memory, so the wrapper change takes effect on the *next* run rather than the
one performing the pull. Keeping `run.sh` small keeps this a non-issue in practice.
This is documented, not engineered around.

## Files touched

- `run.sh` — new wrapper (executable).
- `inky_weather/version.py` — new: `get_version`.
- `inky_weather/render.py` — add `_updated_label`; thread `version` through
  `draw_header` and `render_display`.
- `inky_weather/main.py` — pass `version.get_version()` into `render_display`.
- `tests/test_version.py`, `tests/test_run_sh.py` — new.
- `tests/test_render.py` — `_updated_label` tests.
- `README.md` — auto-update section, crontab change, versioning/tagging docs.
