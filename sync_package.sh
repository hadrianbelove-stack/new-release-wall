#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +"%Y%m%d-%H%M%S")
OUT="NRW_SYNC_${STAMP}.zip"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

REQ_FILES=( complete_project_context.md PROJECT_CHARTER.md PROJECT_LOG.md )
OPT_FILES=(
  ALL_CODE_SYNC.py
  new_release_wall_balanced.py movie_tracker.py generate_site.py curator_admin.py
  scraper_core.py tmdb_auth.py constants.py settings.py
  templates/site.html templates/site_enhanced.html
  output/site/index.html output/data.json output/data_core.json curated_selections.json
  tests/smoke_test.py run_smoke.sh requirements.txt config.yaml
)

# Require all three docs
missing=0
for f in "${REQ_FILES[@]}"; do
  [ -f "$f" ] || { echo "ERROR: missing required $f"; missing=1; }
done
[ $missing -eq 0 ] || exit 2

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
  [ -f output/data.json ] && echo -n "  data.json items: " && jq 'length' output/data.json || echo "  data.json: missing"
  [ -f output/data_core.json ] && echo -n "  data_core.json items: " && jq 'length' output/data_core.json || echo "  data_core.json: missing"
  echo
  echo "Files included:"; for f in "${TOZIP[@]}"; do echo "  $f"; done
} > "$MANI"
TOZIP+=("$MANI")

zip -q -r "$OUT" "${TOZIP[@]}"
shasum -a 256 "$OUT" | awk '{print "SHA256: "$1}' | tee "snapshots/${OUT}.sha256"
echo "Created $OUT"
echo "Manifest: $MANI"