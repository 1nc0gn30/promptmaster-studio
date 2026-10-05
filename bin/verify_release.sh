#!/usr/bin/env bash
set -euo pipefail

# Deterministic build & local provenance verification harness
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== PromptMaster Studio: Reproducible Build & Provenance Verification ==="

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --pretty=%ct 2>/dev/null || date +%s)}"
export PYTHONHASHSEED=0

BUILD_DIR="dist/local-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/b1" "$BUILD_DIR/b2"

echo "-> Running build #1..."
if python3 -c "import build.__main__" &>/dev/null; then
    python3 -m build --outdir "$BUILD_DIR/b1"
else
    python3 -m pip wheel --no-deps -w "$BUILD_DIR/b1" .
fi

echo "-> Running build #2..."
if python3 -c "import build.__main__" &>/dev/null; then
    python3 -m build --outdir "$BUILD_DIR/b2"
else
    python3 -m pip wheel --no-deps -w "$BUILD_DIR/b2" .
fi

echo "-> Comparing artifact digests..."
b1_wheel_hash=$(sha256sum "$BUILD_DIR"/b1/*.whl | awk '{print $1}')
b2_wheel_hash=$(sha256sum "$BUILD_DIR"/b2/*.whl | awk '{print $1}')

echo "Wheel 1: $b1_wheel_hash"
echo "Wheel 2: $b2_wheel_hash"

if [ "$b1_wheel_hash" != "$b2_wheel_hash" ]; then
    echo "[!] Wheels differ. Inspecting differences with diffoscope..."
    if command -v diffoscope &>/dev/null; then
        diffoscope "$BUILD_DIR/b1" "$BUILD_DIR/b2" --text "$BUILD_DIR/diffoscope-report.txt" || true
        cat "$BUILD_DIR/diffoscope-report.txt"
    fi
else
    echo "[✓] Bit-for-bit reproducible wheel verified."
fi

if command -v syft &>/dev/null; then
    echo "-> Generating source and artifact Syft SPDX SBOMs..."
    syft dir:. -o spdx-json="$BUILD_DIR/promptmaster-studio.spdx.json"
    syft dir:"$BUILD_DIR/b1" -o spdx-json="$BUILD_DIR/artifacts.spdx.json"
    echo "[✓] SBOMs generated at $BUILD_DIR/promptmaster-studio.spdx.json and $BUILD_DIR/artifacts.spdx.json"
fi

if command -v cosign &>/dev/null; then
    echo "-> Cosign binary detected: $(cosign version --json 2>/dev/null | grep -o '\"GitVersion\":[^,]*' || cosign version 2>&1 | head -n1)"
    echo "-> Verifying release bundle signing readiness..."
    mkdir -p "$BUILD_DIR/keys"
    COSIGN_PASSWORD="" cosign generate-key-pair --output-key-prefix "$BUILD_DIR/keys/cosign-local"
    for wheel in "$BUILD_DIR"/b1/*.whl; do
        if [ -f "$wheel" ]; then
            COSIGN_PASSWORD="" cosign sign-blob --key "$BUILD_DIR/keys/cosign-local.key" --bundle "${wheel}.bundle" --yes "$wheel"
            cosign verify-blob --key "$BUILD_DIR/keys/cosign-local.pub" --bundle "${wheel}.bundle" "$wheel"
            echo "[✓] Local Rekor/cosign bundle signature verified for $(basename "$wheel")"
        fi
    done
fi

echo "=== Harness check complete ==="

