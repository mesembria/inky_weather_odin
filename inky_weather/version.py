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
