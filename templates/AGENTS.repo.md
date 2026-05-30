# Project Agent Instructions

Replace bracketed fields before relying on this in production.

## Project

- Name: [PROJECT_NAME]
- Goal: [ONE_SENTENCE_PRODUCT_GOAL]
- Primary users: [WHO_THIS_IS_FOR]
- Production URL or app target: [URL_OR_APP_OR_N/A]

## Commands

Install:

```bash
[INSTALL_COMMAND]
```

Run locally:

```bash
[DEV_COMMAND]
```

Test:

```bash
[TEST_COMMAND]
```

Lint or typecheck:

```bash
[LINT_OR_TYPECHECK_COMMAND]
```

Build:

```bash
[BUILD_COMMAND]
```

## Architecture Notes

- [IMPORTANT_DIRECTORY_OR_MODULE]
- [IMPORTANT_DATA_FLOW]
- [IMPORTANT_CONSTRAINT]

## Working Rules

- Prefer existing patterns in this repo.
- Keep edits scoped to the current task.
- Add tests for behavior changes when feasible.
- Run the smallest relevant check first.
- Do not claim completion until the verification command has passed or the blocker is named.

## Safety Boundaries

Ask before:

- Deleting data or files outside the requested scope.
- Running destructive git commands.
- Changing production secrets or production data.
- Triggering irreversible external actions.

Never:

- Print secrets.
- Commit `.env` files.
- Hide failing tests.

## Definition Of Done

A task is done when:

- The requested behavior or artifact exists.
- Relevant tests/checks have passed.
- Any user-facing change has been visually or manually verified when applicable.
- The final answer names files changed, checks run, and remaining risk.
