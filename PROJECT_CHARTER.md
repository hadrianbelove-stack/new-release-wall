# PROJECT_CHARTER.md

Immutable Charter — edits only via AMENDMENT blocks.

## Vision
Blockbuster wall for streaming age.

## Core Strategy
Provider availability = ground truth.
Track all releases. Curate later via admin.

## Invariants
RULE-001: No code deletions without APPROVED: DELETE.
RULE-002: Always offer multiple options with pros/cons.
RULE-003: Context docs are append-only (no silent rewrites).

## Current Architecture
- movie_tracker.py: persistent database
- new_release_wall_balanced.py: direct scraper
- scraper_core.py: TMDB helpers + auth
- curator_admin.py: web curation panel
- templates/: site.html + site_enhanced.html
- output/: data.json, data_core.json, site/

## Command Cheatsheet
```bash
python3 new_release_wall_balanced.py --region US --days 14 --max-pages 2
python3 new_release_wall_balanced.py --region US --days 14 --max-pages 2 --use-core --core-limit 5
python3 movie_tracker.py daily
python3 curator_admin.py
python3 generate_site.py
```

## TMDB Keys Required
Export TMDB_BEARER or configure config.yaml with tmdb.bearer.

## Data Flow
1. Scraper → output/data.json (baseline) + output/data_core.json (enriched)
2. Tracker → movie_tracking.json (persistent database)
3. Generator → output/site/index.html (public site)
4. Admin → curator interface for visibility/featuring

## Authentication Strategy
Hybrid auth resolver (tmdb_auth.py):
Priority: TMDB_BEARER env → TMDB_API_KEY env → config.yaml variants

---

## Session Handoff Checklist (Immutable Section)

At end of each work session:

1. Run smoke tests (baseline + core).
2. Verify outputs exist:
   - output/data.json
   - output/data_core.json
   - output/site/index.html
3. Ensure required docs exist:
   - complete_project_context.md
   - PROJECT_CHARTER.md
   - PROJECT_LOG.md
4. Run `./sync_package.sh` to produce:
   - NRW_SYNC_<timestamp>.zip
   - Manifest (.manifest.txt)
   - SHA256 (.sha256)
5. Upload NRW_SYNC_*.zip + manifest + sha256 to next session.

This guarantees continuity across assistants and prevents drift.


**Magic Word:** RESUME NRW  
Upload the latest NRW_SYNC_<timestamp>.zip, plus manifest and sha256.
