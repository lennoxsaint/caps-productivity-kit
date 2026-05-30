# Example: Feature Build

Use this when a product change needs implementation and verification.

## Conductor Start

```text
Use .caps/prompts/conductor.md.
Goal: Add saved filters to the customer table.
Done means: users can save, rename, apply, and delete filters; tests pass; UI is verified on desktop and mobile.
```

## Worker: Implementation

```text
Use .caps/prompts/workers/implementation.md.

Objective: Implement saved filters for the customer table.
Allowed files:
- src/features/customers/**
- tests/customers/**

Commands:
- npm test -- customers
- npm run typecheck

Stop if the change requires a database migration not already approved.
```

## Worker: QA

```text
Use .caps/prompts/workers/qa.md.

Objective: Verify saved filters from the user's point of view.
Check:
- Save a filter
- Rename it
- Apply it after refresh
- Delete it
- Mobile viewport still works

Return pass/fail with exact reproduction steps for any bug.
```

## Final Handoff

```text
Status: done

Changed:
- Added saved filter CRUD in customer table.

Verified:
- npm test -- customers passed.
- npm run typecheck passed.
- Desktop and mobile manual QA passed.

Risk:
- No production migration included.

Next:
- Ship behind the existing beta flag.
```
