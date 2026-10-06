#!/usr/bin/env bash
# Verification helper for Sigstore cosign Rekor provenance bundles, SHA256 checksums, and Syft SPDX SBOMs.
set -euo pipefail

DIST_DIR="${1:-dist/release}"
REPO="${GITHUB_REPOSITORY:-1nc0gn30/promptmaster-studio}"
ISSUER="https://token.actions.githubusercontent.com"
CERT_REGEXP="https://github.com/${REPO}/.github/workflows/release.yml@refs/.*"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "Usage: $0 [dist_directory]"
  echo "Verifies SHA256SUMS, Cosign Rekor provenance bundles, and Syft SPDX SBOMs."
  exit 0
fi

if [ ! -d "$DIST_DIR" ]; then
  echo "Error: Directory '$DIST_DIR' not found." >&2
  exit 1
fi

echo "==> Verifying SHA256SUMS in $DIST_DIR..."
if [ -f "$DIST_DIR/SHA256SUMS" ]; then
  (cd "$DIST_DIR" && sha256sum --check --ignore-missing SHA256SUMS)
fi

echo "==> Verifying Sigstore Cosign Rekor provenance bundles..."
for bundle in "$DIST_DIR"/*.bundle; do
  [ -e "$bundle" ] || continue
  target="${bundle%.bundle}"
  if [ -f "$target" ]; then
    echo "Verifying $target..."
    cosign verify-blob \
      --bundle "$bundle" \
      --rekor-url "https://rekor.sigstore.dev" \
      --certificate-identity-regexp "$CERT_REGEXP" \
      --certificate-oidc-issuer "$ISSUER" \
      "$target"
  fi
done

echo "==> Verifying SPDX SBOM availability..."
for sbom in "$DIST_DIR"/*.spdx.json; do
  [ -e "$sbom" ] || continue
  echo "Found SBOM: $sbom"
done

echo "==> Verifying reproducible build report..."
if [ -f "$DIST_DIR/reproducibility-report.txt" ]; then
  echo "Found reproducibility report: $DIST_DIR/reproducibility-report.txt"
  if [ -s "$DIST_DIR/reproducibility-report.txt" ]; then
    echo "[-] Warning/Failure: Non-empty diffoscope report detected in $DIST_DIR/reproducibility-report.txt" >&2
    cat "$DIST_DIR/reproducibility-report.txt" >&2
    exit 1
  else
    echo "[✓] Reproducibility report confirms bit-for-bit identical build outputs (diffoscope diff is clean)."
  fi
else
  echo "[!] Notice: $DIST_DIR/reproducibility-report.txt not found. Skipping diffoscope check."
fi

echo "==> Verification completed successfully."
