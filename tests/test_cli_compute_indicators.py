"""CLI smoke tests for compute-indicators."""
from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "compute-indicators", *args],
        capture_output=True,
        text=True,
    )


def test_unknown_strategy_exits_nonzero():
    result = _run("--strategy", "nonexistent_strategy_xyz")
    assert result.returncode != 0
    assert "unknown strategy" in result.stderr.lower() or "unknown strategy" in result.stdout.lower()


def test_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    assert "--strategy" in result.stdout
