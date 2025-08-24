# PROJECT LOG — APPEND-ONLY SESSION HISTORY

## 2025-08-22 Anti-Drift Guardrails Setup
- Created PROJECT_CHARTER.md with immutable operating rules
- Installed git hooks: pre-commit (conflict markers) + commit-msg (approval tokens)
- Added .vscode/settings.json for safer editing
- Created golden-2025-08-22 branch and tag for snapshot
- Setup anti-drift guardrails branch with complete governance framework
## [2025-08-23] Anti-Drift & Cleanup
- Unified TMDB auth via request_tmdb(); removed duplicate class.
- Core enrichment working (10 records in data_core.json in latest run).
- Added caching/backoff; providers-only fast path.
- Curator admin upgraded to flip-card UI with bulk actions.
- Added smoke test and menu hook for admin.

