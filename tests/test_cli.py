from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fixtures import ROOT, make_project


def _run(config_path: Path, extra=()):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "dataguard",
            "--config",
            str(config_path),
            "--output-dir",
            str(config_path.parent / "out"),
            "--db",
            str(config_path.parent / "dq.sqlite"),
            *extra,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_exit_code_and_no_fail(tmp_path: Path):
    config_path = make_project(tmp_path)
    failed = _run(config_path)
    assert failed.returncode == 1, failed.stderr
    no_fail = _run(config_path, ["--no-fail"])
    assert no_fail.returncode == 0, no_fail.stderr
    assert "summary" in no_fail.stdout
