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

- The current conductor thread.
- Active worker threads.
- Release or incident threads that are still open.

Unpin or archive:

- Completed worker threads after their output is captured.
- Old planning threads that no longer own a decision.
- Duplicate or abandoned attempts.

## Why It Matters

Codex work gets messy when every thread is named like a diary entry. CAPS names make the action visible before you open the tab.
