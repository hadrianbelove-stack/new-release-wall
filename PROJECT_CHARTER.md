# PROJECT CHARTER — IMMUTABLE OPERATING RULES
Status: Active • Effective: 2025-08-22

## A. Anti-Drift Contract
1) Default mode = **EDIT REQUEST**. Treat every ask as a code-edit request unless the message starts with `DISCUSS ONLY`.
2) Output format = **unified diff patch only** for any change to code or docs.
3) **No deletions** unless the message contains the literal token: `APPROVED: DELETE`.
4) **No context rewrites.** This Charter is immutable. Changes require an Amendment (C) and `APPROVED: CONTEXT-EDIT`.
5) **State verification.** If pasted code or file hash seems inconsistent, stop and ask for the exact path/lines.
6) **Options required.** For non-trivial work: present 2–3 options with pros/cons and one recommendation.
7) **Ground truth.** Provider availability determines inclusion. Do not re-introduce release-type filtering.

## B. Edit Protocol (automatic)
When a message mentions files, functions, or behavior:
- Read the pasted snippet(s).
- Return **one fenced block** containing a valid unified diff for those exact paths.
- If more context is needed, ask for file path and line range. Do not guess.

## C. Amendments (how this file can change)
Assistants must propose changes using this format:
Apply only when the user's reply includes `APPROVED: CONTEXT-EDIT`.  
Append approved items to **Amendments.log** at the end of this file.

## D. Approval Tokens
- `APPROVED: DELETE` — allow code deletions in a diff.
- `APPROVED: CONTEXT-EDIT` — allow Charter/Context changes via Amendment.

## E. Working Memory Hygiene
Keep summaries terse. Refer to file paths and line ranges. Push detail to `PROJECT_LOG.md`.

## F. Non-negotiables
No silent scope creep. No speculative refactors. No renaming without explicit request.

---

## Amendments.log
<!-- Append approved amendments here in chronological order. -->

## G. Workflow & Templates

### Daily Workflow
1. Work normally — every request is treated as an **EDIT REQUEST** unless you say `DISCUSS ONLY`.
2. At the **end of session**, type `END SESSION`.  
   → Assistant will generate a new `PROJECT_LOG.md` entry in the correct format.  
   → You paste it at the **top** of `PROJECT_LOG.md`.
3. If you forget, start of next session you can say "make a log entry for yesterday" and the assistant will reconstruct it.

### Log Entry Template
Use this template when adding to `PROJECT_LOG.md` (assistant will fill it in for you):

```
## YYYY-MM-DD
- Summary of changes made
- Key files touched
- Any consolidations/archives
- Next steps or pending work
```

### One-Command Sync File Refresh
```bash
./scripts/rebuild_sync.sh
git add ALL_CODE_SYNC.py ALL_CODE_SYNC.py.sha256 ALL_CODE_SYNC.py.filelist
git commit -m "Refresh ALL_CODE_SYNC bundle"
git push
```