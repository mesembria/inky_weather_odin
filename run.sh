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
