#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +"%Y%m%d-%H%M%S")
OUT="NRW_SYNC_${STAMP}.zip"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

REQ_FILES=(
  complete_project_context.md      # required
)

OPT_FILES=(
  ALL_CODE_SYNC.py
  PROJECT_LOG.md
  templates/site.html
  templates/site_enhanced.html
  output/site/index.html
  output/data.json
  output/data_core.json
  curated_selections.json
  new_release_wall_balanced.py
  scraper_core.py
  tmdb_auth.py
  constants.py
  settings.py
  curator_admin.py
  tests/smoke_test.py
  run_smoke.sh
)

# Verify required files
missing=0
for f in "${REQ_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: required file missing: $f" >&2
    missing=1
  fi
done
if [ $missing -ne 0 ]; then
  echo "Aborting sync: add the missing required file(s) and re-run." >&2
  exit 2
fi

# Collect files that exist
TOZIP=()
for f in "${REQ_FILES[@]}" "${OPT_FILES[@]}"; do
  [ -f "$f" ] && TOZIP+=("$f")
done

mkdir -p snapshots
MANI="snapshots/MANIFEST_${STAMP}.txt"
{
  echo "New Release Wall — Sync Manifest"
  echo "Timestamp: $STAMP"
  echo "Branch: $BRANCH"
  echo "Commit: $SHA"
  echo
  echo "Counts:"
  if [ -f output/data.json ]; then echo -n "  data.json items: " && jq 'length' output/data.json; else echo "  data.json: missing"; fi
  if [ -f output/data_core.json ]; then echo -n "  data_core.json items: " && jq 'length' output/data_core.json; else echo "  data_core.json: missing"; fi
  echo
  echo "Files included:"
  for f in "${TOZIP[@]}"; do echo "  $f"; done
} > "$MANI"
TOZIP+=("$MANI")

zip -q -r "$OUT" "${TOZIP[@]}"
shasum -a 256 "$OUT" | awk '{print "SHA256: "$1}' | tee "snapshots/${OUT}.sha256"
echo "Created $OUT"
echo "Manifest: $MANI"