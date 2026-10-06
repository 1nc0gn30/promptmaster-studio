"""Tests for release provenance verification script and reproducible build artifacts."""

import os
import subprocess
from pathlib import Path


def test_verify_provenance_script_help():
    """Test that scripts/verify_provenance.sh displays usage with -h."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_provenance.sh"
    assert script_path.exists()
    assert os.access(script_path, os.X_OK)

    result = subprocess.run(
        [str(script_path), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "SHA256SUMS" in result.stdout
    assert "Cosign" in result.stdout
    assert "SPDX" in result.stdout


def test_verify_provenance_script_missing_dir():
    """Test that scripts/verify_provenance.sh cleanly fails when target dir is missing."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_provenance.sh"
    result = subprocess.run(
        [str(script_path), "non_existent_dist_dir_12345"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr
