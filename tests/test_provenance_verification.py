"""Tests for release provenance verification script and reproducible build artifacts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


def _run_bash_script(script_path: Path, *args: str) -> subprocess.CompletedProcess:
    if sys.platform.startswith("win"):
        bash_bin = shutil.which("bash")
        if not bash_bin:
            pytest.skip("bash not available on Windows")
        cmd = [bash_bin, str(script_path), *args]
    else:
        cmd = [str(script_path), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_verify_provenance_script_help():
    """Test that scripts/verify_provenance.sh displays usage with -h."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_provenance.sh"
    assert script_path.exists()
    if not sys.platform.startswith("win"):
        assert os.access(script_path, os.X_OK)

    result = _run_bash_script(script_path, "--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "SHA256SUMS" in result.stdout
    assert "Cosign" in result.stdout
    assert "SPDX" in result.stdout


def test_verify_provenance_script_missing_dir():
    """Test that scripts/verify_provenance.sh cleanly fails when target dir is missing."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_provenance.sh"
    result = _run_bash_script(script_path, "non_existent_dist_dir_12345")
    assert result.returncode == 1
    assert "not found" in result.stderr
