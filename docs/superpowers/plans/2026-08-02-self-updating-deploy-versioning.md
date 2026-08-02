# Self-Updating Deploy + Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Pi self-update from `origin/main` before each hourly run, and give the code a git-derived version visible in the log and on the panel.

**Architecture:** A wrapper script (`run.sh`) that cron invokes updates the checkout (hard reset to `origin/main`, reinstall deps if `requirements.txt` changed) and then `exec`s `python -m inky_weather.main`, so the freshly-pulled code runs this cycle. A `version.get_version()` helper reports `git describe --tags --always --dirty`, threaded into the header.

**Tech Stack:** Python 3.13, Pillow, `subprocess`; Bash + git for the wrapper; pytest with `unittest.mock`.

## Global Constraints

- **Update strategy:** `git fetch --quiet $REMOTE $BRANCH` then `git reset --hard --quiet FETCH_HEAD`. Hard reset to latest `main`; gitignored `config.py`/state are safe.
- **`run.sh` must** use `set -uo pipefail` but NOT `set -e` (continue past a failed fetch); derive the repo dir from `${BASH_SOURCE[0]}`; honor env overrides `INKY_PYTHON`, `INKY_PIP`, `INKY_RUN_CMD` (default `$PY -m inky_weather.main`), `INKY_REMOTE` (default `origin`), `INKY_BRANCH` (default `main`); reinstall deps only when `git hash-object requirements.txt` changed; and end with `exec $RUN_CMD`.
- **Version string:** `git describe --tags --always --dirty`; `get_version()` returns `"unknown"` on empty output or any exception.
- **Version surfaced:** a one-line log summary in `run.sh` AND appended to the header's updated line as `" · <version>"`.
- **Header separator** is `" · "` — the middle dot U+00B7, exactly as in the existing `render.py` code. Do not substitute a hyphen or bullet.
- **Deps reinstall** happens only when `requirements.txt` actually changed in the update.
- Tests: pytest, `unittest.mock`; the `run.sh` test skips when `git`/`bash` are unavailable. Run with `.venv/bin/python -m pytest` (pytest.ini sets `-p no:debugging`).

---

### Task 1: Git-derived version helper

**Files:**
- Create: `inky_weather/version.py`
- Test: `tests/test_version.py`

**Interfaces:**
- Produces: `version.get_version() -> str` — `git describe --tags --always --dirty` for the repo, or `"unknown"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_version.py`:

```python
from unittest import mock

from inky_weather import version


def test_get_version_returns_stripped_stdout():
    cp = mock.Mock(stdout="v1.0.0\n")
    with mock.patch("inky_weather.version.subprocess.run", return_value=cp):
        assert version.get_version() == "v1.0.0"


def test_get_version_empty_stdout_returns_unknown():
    cp = mock.Mock(stdout="\n")
    with mock.patch("inky_weather.version.subprocess.run", return_value=cp):
        assert version.get_version() == "unknown"


def test_get_version_exception_returns_unknown():
    with mock.patch("inky_weather.version.subprocess.run",
                    side_effect=FileNotFoundError):
        assert version.get_version() == "unknown"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_version.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inky_weather.version'`.

- [ ] **Step 3: Create the version module**

Create `inky_weather/version.py`:

```python
"""Report the running code's version via `git describe` (zero-maintenance)."""
import os
import subprocess

_ROOT = os.path.dirname(os.path.dirname(__file__))


def get_version():
    """Return `git describe --tags --always --dirty` for this repo, or 'unknown'.

    Zero-maintenance version string: the short commit SHA before any tags exist,
    a tag like `v1.2.0` on a tagged commit, or `v1.2.0-3-gabc1234` past a tag.
    Returns 'unknown' if git is unavailable or this isn't a checkout.
    """
    try:
        out = subprocess.run(
            ["git", "-C", _ROOT, "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_version.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add inky_weather/version.py tests/test_version.py
git commit -m "feat: add git-derived version reporting"
```

---

### Task 2: Show the version in the header

**Files:**
- Modify: `inky_weather/render.py` (add `_updated_label`; add `version=None` to `draw_header` and `render_display`)
- Modify: `inky_weather/main.py` (import `version`; pass it into `render_display`)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `version.get_version()` (Task 1).
- Produces: `render._updated_label(updated_str, version=None) -> str`; `render.draw_header(draw, location, date_str, updated_str, badge, version=None)`; `render.render_display(..., version=None)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py` (note the separator is the middle dot `·`, U+00B7, matching the existing code):

```python
def test_updated_label_without_version():
    assert render._updated_label("9:08pm") == "9:08pm · NEXT 12H"


def test_updated_label_with_version():
    assert render._updated_label("9:08pm", "v1.0.0") == "9:08pm · NEXT 12H · v1.0.0"


def test_draw_header_renders_version_when_given():
    img1, d1 = _blank()
    render.draw_header(d1, "Town", "Tue Jun 30", "10:02 AM", None)
    img2, d2 = _blank()
    render.draw_header(d2, "Town", "Tue Jun 30", "10:02 AM", None, "v9.9.9")
    assert img1.tobytes() != img2.tobytes()   # version text is actually drawn
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -k "updated_label or renders_version" -v`
Expected: FAIL — `AttributeError: module 'inky_weather.render' has no attribute '_updated_label'` (and `draw_header` doesn't yet accept a version argument).

- [ ] **Step 3: Add `_updated_label` and thread version through render**

In `inky_weather/render.py`, add `_updated_label` immediately above `draw_header`:

```python
def _updated_label(updated_str, version=None):
    """The header's updated-time line, optionally suffixed with the running version."""
    base = updated_str + " · NEXT 12H"
    return base + " · " + version if version else base
```

Change the `draw_header` signature to accept `version=None`:

```python
def draw_header(draw, location, date_str, updated_str, badge, version=None):
```

Replace its updated-time line (currently `_ctext(draw, updated_str + " · NEXT 12H", ...)`) with:

```python
    _ctext(draw, _updated_label(updated_str, version), WIDTH - 20, 30, display_font(12, 600), INK, anchor="rm")
```

Change the `render_display` signature to accept `version=None` and pass it to `draw_header`:

```python
def render_display(hours, bands, hour_icons, cards, badge,
                   location_name, date_str, updated_str, version=None):
```

and its `draw_header` call:

```python
    draw_header(draw, location_name, date_str, updated_str, badge, version)
```

- [ ] **Step 4: Wire the version into `main.build_image`**

In `inky_weather/main.py`, add `version` to the package import (line 7):

```python
from . import weather, icons, render, advice, history, cache, version
```

In `build_image`, add the `version` argument to the `render.render_display(...)` call (currently ending with the `updated_str=...` line):

```python
    return render.render_display(
        hours, bands, hour_icons, cards, badge,
        location_name=cfg.get("location_name", ""),
        date_str=now.strftime("%a %b %-d"),
        updated_str=now.strftime("%-I:%M%p").lower().lstrip("0"),
        version=version.get_version(),
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py tests/test_smoke.py -v`
Expected: PASS — new header tests pass, and pre-existing `render`/`smoke` tests (which call `draw_header`/`render_display` without a version) still pass because `version` defaults to `None`.

- [ ] **Step 6: Commit**

```bash
git add inky_weather/render.py inky_weather/main.py tests/test_render.py
git commit -m "feat: show running version in the header"
```

---

### Task 3: Self-updating `run.sh` wrapper

**Files:**
- Create: `run.sh` (repo root, executable)
- Test: `tests/test_run_sh.py`

**Interfaces:**
- Produces: `run.sh` — cron entry point. Honors env overrides `INKY_PYTHON`, `INKY_PIP`, `INKY_RUN_CMD`, `INKY_REMOTE`, `INKY_BRANCH`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_run_sh.py`:

```python
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SH = os.path.join(REPO, "run.sh")

pytestmark = pytest.mark.skipif(
    not shutil.which("git") or not shutil.which("bash"),
    reason="git and bash required")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def _make_origin_and_clone(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "config", "user.email", "t@t")
    _git(origin, "config", "user.name", "t")
    (origin / "requirements.txt").write_text("requests\n")
    shutil.copy(RUN_SH, origin / "run.sh")
    os.chmod(origin / "run.sh", 0o755)
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "init")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    _git(clone, "config", "user.email", "t@t")
    _git(clone, "config", "user.name", "t")
    return origin, clone


def _run(clone, **env):
    e = dict(os.environ)
    e.update(env)
    return subprocess.run(["bash", str(clone / "run.sh")], cwd=str(clone),
                          capture_output=True, text=True, env=e)


def test_updates_to_new_origin_commit_and_runs(tmp_path):
    origin, clone = _make_origin_and_clone(tmp_path)
    (origin / "marker.txt").write_text("v2\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "v2")
    ran = clone / "ran.marker"
    r = _run(clone, INKY_RUN_CMD="touch {}".format(ran))
    assert ran.exists()                     # run command exec'd last
    assert (clone / "marker.txt").exists()  # clone hard-reset to new origin commit
    assert "updated" in r.stdout


def test_up_to_date_when_no_new_commit(tmp_path):
    origin, clone = _make_origin_and_clone(tmp_path)
    ran = clone / "ran.marker"
    r = _run(clone, INKY_RUN_CMD="touch {}".format(ran))
    assert ran.exists()
    assert "up to date" in r.stdout


def test_offline_still_runs(tmp_path):
    origin, clone = _make_origin_and_clone(tmp_path)
    ran = clone / "ran.marker"
    r = _run(clone, INKY_REMOTE=str(tmp_path / "does-not-exist"),
             INKY_RUN_CMD="touch {}".format(ran))
    assert ran.exists()                     # ran despite fetch failure
    assert "fetch failed" in r.stdout


def test_requirements_change_triggers_reinstall(tmp_path):
    origin, clone = _make_origin_and_clone(tmp_path)
    (origin / "requirements.txt").write_text("requests\nPillow\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-q", "-m", "add dep")
    pip_marker = clone / "pip.marker"
    pip_stub = tmp_path / "pip-stub.sh"
    pip_stub.write_text("#!/usr/bin/env bash\ntouch {}\n".format(pip_marker))
    os.chmod(pip_stub, 0o755)
    ran = clone / "ran.marker"
    r = _run(clone, INKY_PIP=str(pip_stub),
             INKY_RUN_CMD="touch {}".format(ran))
    assert "reinstalling" in r.stdout
    assert pip_marker.exists()              # stub pip was invoked
    assert ran.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_run_sh.py -v`
Expected: FAIL — `shutil.copy` raises `FileNotFoundError` because `run.sh` doesn't exist yet (or the tests error in setup).

- [ ] **Step 3: Create `run.sh`**

Create `run.sh` at the repo root:

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

Make it executable so git records mode `100755`:

```bash
chmod +x run.sh
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_run_sh.py -v`
Expected: PASS (4 tests; or skipped if `git`/`bash` are unavailable).

- [ ] **Step 5: Commit**

```bash
git add run.sh tests/test_run_sh.py
git commit -m "feat: add self-updating run.sh wrapper for cron"
```

Verify the executable bit was recorded (should show `100755`):

```bash
git ls-files -s run.sh
```

---

### Task 4: Document auto-update and versioning in the README

**Files:**
- Modify: `README.md` (replace the "Schedule (hourly refresh)" section)

**Interfaces:** none — documentation only.

- [ ] **Step 1: Replace the Schedule section**

In `README.md`, replace this exact block:

````markdown
## Schedule (hourly refresh)
Add to crontab (`crontab -e`), using the venv's Python:
```
0 * * * * cd /home/pi/inky_weather_odin && /home/pi/inky_weather_odin/.venv/bin/python -m inky_weather.main >> /home/pi/weather.log 2>&1
```
````

with:

````markdown
## Schedule (hourly refresh)

The Pi runs via `run.sh`, a wrapper that self-updates the checkout from
`origin/main` before each run, then renders. Make it executable once:
```bash
chmod +x run.sh
```
Add to crontab (`crontab -e`):
```
0 * * * * /home/pi/inky_weather_odin/run.sh >> /home/pi/weather.log 2>&1
```

### Auto-update

Each run, `run.sh`:
1. `git fetch` + `git reset --hard origin/main` — the Pi always matches the latest
   `main`. Your `config.py`, history, and cached image are gitignored, so the reset
   never touches them.
2. Reinstalls dependencies only if `requirements.txt` changed in that update.
3. If the network is down (fetch fails), it skips the update and runs the code
   already on disk — the display never goes dark over a failed pull.

It logs one line per run to `weather.log`, e.g.
`… update: weather abc1234 -> def5678 (updated)` or `… (up to date)`.

Caveat: if a push changes `run.sh` itself, the new wrapper takes effect on the
*next* run (bash has already read the running copy).

### Versioning

The running version is `git describe --tags --always --dirty` — the short commit
SHA until you tag, then the tag name. It appears in the log line above and in the
top-right of the panel header (after the "updated" time). To cut a named release:
```bash
git tag v1.0.0 && git push --tags
```
After that the panel and log show `v1.0.0` (or e.g. `v1.0.0-3-gabc1234` three
commits later).
````

- [ ] **Step 2: Verify the section reads correctly**

Run: `sed -n '/## Schedule/,/## Development/p' README.md`
Expected: the new Schedule + Auto-update + Versioning content, immediately followed by the unchanged `## Development (on a Mac)` heading.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document run.sh auto-update and versioning"
```

---

## Notes for the implementer

- **Why the `run.sh` test copies the script into a temp git repo:** the wrapper's real work is git plumbing. Testing it against throwaway origin/clone repos with `INKY_RUN_CMD`/`INKY_PIP` stubs exercises the actual update logic without needing the venv or the `inky_weather` package present in the temp repo.
- **`FETCH_HEAD` vs `origin/main`:** after `git fetch origin main`, `FETCH_HEAD` is the just-fetched tip; resetting to it avoids depending on remote-tracking ref configuration in the temp clones.
- **Middle dot:** the header separator `·` is U+00B7, already used in `render.py`. Keep it identical so the test string comparison matches.
