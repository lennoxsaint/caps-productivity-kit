# Lane: Mission Control

Use this as the conductor lane for a generic cohort-launch operating system.

## Objective

Coordinate cohort-launch work across bounded lanes while preserving public-safe
boundaries.

## Rules

- Route to existing active lanes before creating new lanes.
- Keep private cohort content out of public artifacts.
- Do not claim live member-facing proof from local drafts or logs.
- Do not assume shell install created, named, or pinned lanes. Use
  thread-control tools later only when the active Codex runtime exposes them.
- Backfeed reusable CAPS patterns with `public_repo_sync_recommendation`.

## Output

Return:

- Active lanes.
- Blockers.
- Next action.
- Public/private boundary notes.
- public_repo_sync_recommendation: yes/no.
