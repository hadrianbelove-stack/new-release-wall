#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/Downloads/new-release-wall}"

# Locate latest sync artifacts
ZIP="$(ls -1t "$ROOT"/NRW_SYNC_*.zip 2>/dev/null | head -1 || true)"
SHA="$(ls -1t "$ROOT"/snapshots/NRW_SYNC_*.sha256 2>/dev/null | head -1 || true)"
MANI="$(ls -1t "$ROOT"/snapshots/MANIFEST_*.txt 2>/dev/null | head -1 || true)"

if [ -z "${ZIP}" ]; then
  echo "No NRW_SYNC_*.zip found. Run ./sync_package.sh first."; exit 2
fi

echo "Latest package:"
echo "  ZIP:  ${ZIP}"
[ -n "${SHA}" ]  && echo "  SHA:  ${SHA}"
[ -n "${MANI}" ] && echo "  MANI: ${MANI}"
echo

# Copy magic word to clipboard if available
if command -v pbcopy >/dev/null 2>&1; then
  printf "RESUME NRW" | pbcopy
  echo 'Magic word copied to clipboard: RESUME NRW'
fi

# Verify SHA if available (best-effort)
if [ -n "${SHA}" ]; then
  calc="$(shasum -a 256 "$ZIP" | awk '{print $1}')"
  ref="$(sed -n 's/^SHA256:\s\+//p' "$SHA" | head -1)"
  if [ -n "$ref" ] && [ "$calc" = "$ref" ]; then
    echo "SHA256 check: OK"
  else
    echo "SHA256 check: WARNING (mismatch or missing). Use file shown above."
  fi
fi

# Open folder for quick drag‑and‑drop
if command -v open >/dev/null 2>&1; then open "$(dirname "$ZIP")"; fi
echo
echo "Next chat steps:"
echo "  1) Say: RESUME NRW"
echo "  2) Attach: $(basename "$ZIP")"
[ -n "${SHA}" ]  && echo "  3) Attach: $(basename "$SHA")"
[ -n "${MANI}" ] && echo "  4) Attach: $(basename "$MANI")"