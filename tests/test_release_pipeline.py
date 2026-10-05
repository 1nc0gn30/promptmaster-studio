import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_release_workflow_hardening():
    release_workflow = REPO_ROOT / ".github" / "workflows" / "release.yml"
    assert release_workflow.is_file(), "Release workflow (.github/workflows/release.yml) must exist"

    content = release_workflow.read_text(encoding="utf-8")
    assert "syft" in content, "Workflow must include Syft SPDX SBOM generation"
    assert "spdx-json" in content, "Workflow must emit SPDX JSON format"
    assert "cosign sign-blob" in content, "Workflow must sign artifacts with Cosign"
    assert "--bundle" in content, "Workflow must produce Cosign Rekor provenance bundles"
    assert "diffoscope" in content, "Workflow must include diffoscope reproducible build analysis"
    assert "SOURCE_DATE_EPOCH" in content, "Workflow must configure deterministic timestamps"


def test_verify_release_script_hardening():
    verify_script = REPO_ROOT / "bin" / "verify_release.sh"
    assert verify_script.is_file(), "bin/verify_release.sh harness must exist"
    assert (verify_script.stat().st_mode & 0o111) != 0, "bin/verify_release.sh must be executable"

    script_text = verify_script.read_text(encoding="utf-8")
    assert "diffoscope" in script_text, "Harness must support diffoscope reproducibility inspections"
    assert "spdx-json" in script_text, "Harness must emit Syft SPDX SBOMs"
    assert "cosign" in script_text, "Harness must verify Cosign bundle signing"
    assert "--bundle" in script_text, "Harness must produce Rekor bundle envelopes"
    assert "SOURCE_DATE_EPOCH" in script_text, "Harness must set deterministic build epochs"

