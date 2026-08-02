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
