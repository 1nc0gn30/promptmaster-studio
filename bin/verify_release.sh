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
if python3 -c "import build" &>/dev/null; then
    python3 -m build --outdir "$BUILD_DIR/b1"
else
    python3 -m pip wheel --no-deps -w "$BUILD_DIR/b1" .
fi

echo "-> Running build #2..."
if python3 -c "import build" &>/dev/null; then
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
    echo "[!] Wheels differ. Checking with diffoscope if present..."
    if command -v diffoscope &>/dev/null; then
        diffoscope "$BUILD_DIR/b1" "$BUILD_DIR/b2" || true
    fi
else
    echo "[✓] Bit-for-bit reproducible wheel verified."
fi

if command -v syft &>/dev/null; then
    echo "-> Generating local Syft SPDX SBOM..."
    syft dir:. -o spdx-json="$BUILD_DIR/promptmaster-studio.spdx.json"
    echo "[✓] SBOM generated at $BUILD_DIR/promptmaster-studio.spdx.json"
fi

if command -v cosign &>/dev/null; then
    echo "-> Cosign binary detected. Signature and Rekor bundle verification available."
fi

echo "=== Harness check complete ==="
