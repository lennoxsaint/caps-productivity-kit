# Naming And Pinning

CAPS thread names should make the active work obvious at a glance.

## Format

Use uppercase, action-first names:

```text
ACTION OBJECT CONTEXT
```

Examples:

```text
BUILD CHECKOUT FIX
QA MOBILE NAV
REVIEW PR 42
DOCS INSTALL GUIDE
SHIP MAY RELEASE
RESEARCH OPENAI API
```

## Good Actions

- `BUILD` for implementation.
- `QA` for verification.
- `REVIEW` for critique and risk.
- `DOCS` for documentation.
- `RESEARCH` for fact-finding.
- `SHIP` for release coordination.
- `TRIAGE` for incidents.
- `PLAN` for ambiguous strategy.

## Pinning Rules

Pin:

- `CAPS CONDUCTOR`, the first conductor thread created by the bootstrap.
- The current conductor thread.
- Active worker threads.
- Release or incident threads that are still open.

Unpin or archive:

- Completed worker threads after their output is captured.
- Old planning threads that no longer own a decision.
- Duplicate or abandoned attempts.

## Lane Lifecycle

Use these states when reporting pinned work:

| State | Meaning |
| --- | --- |
| `active` | The lane is being worked now or should keep progressing. |
| `waiting` | The lane is clear, but paused on the user, a tool, or proof. |
| `blocked` | The lane cannot continue without a named gate. |
| `source/reference` | The thread is useful context, not active work. |
| `unpin-ready` | The decision or output is captured and the thread can leave today view. |
| `archived/done` | The work is closed and no sidebar attention is needed. |

Do not keep source/reference threads pinned just because they are interesting.
Pinning is an attention claim. If it is not today work, capture the useful
context and recommend unpinning.

When thread-control tools are available, the conductor should title and pin a
new worker immediately after `create_thread` returns an id. If title or pin
mutation is unavailable, report the exact skipped step and give manual
instructions.

## Why It Matters

Codex work gets messy when every thread is named like a diary entry. CAPS names make the action visible before you open the tab.
