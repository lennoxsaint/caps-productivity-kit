# Naming And Pinning

CAPS thread names should make the active work obvious at a glance.

Titles are coordination metadata. They are not proof that work ran, passed,
merged, deployed, shipped, or became live.

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

## Project and category emoji

The optional title-sync policy uses this precedence:

1. explicit thread emoji override;
2. project emoji preference;
3. task-category emoji preference;
4. no emoji.

Edit `.caps/config/title-preferences.json` after installation. An explicit
owner title or emoji persists until changed or cleared. Automatic reconciliation
does not rewrite existing pinned titles merely to add an emoji; it waits for a
material, evidence-supported task-state change.

## Evidence-gated title sync

The paused `caps-pinned-title-sync` automation template is a project-local cron
task that runs on Luna low every twenty minutes. It is deliberately not a
thread-bound heartbeat: native heartbeat tasks cannot carry an independent
model, project, or working-directory contract. Native pin, title, or task-state
events should trigger the same policy sooner when the runtime supports them.
Events complement the sweep; they do not replace it.

The policy engine:

- inspects active pinned threads only;
- discovers the single case-insensitive `Pinned` section through native
  `threadSection/list`, then uses `thread/list` with its `sectionId`;
- falls back to the legacy `isPinned=true`/`useStateDbOnly=true` query only when
  the section method returns legacy JSON-RPC `-32600` or method-not-found
  `-32601`;
- fails closed on missing, ambiguous, or empty-unverified sections and
  mismatched row membership; an empty section cannot prove that legacy pin
  metadata was migrated;
- fails closed when the installed Codex app-server omits pin metadata or ignores
  the pin filter; it never substitutes an unfiltered history scan;
- requires a new task-state revision and evidence references;
- preserves owner wording and manual overrides;
- rejects unverified completion language;
- makes event and sweep decisions idempotent;
- rate-limits automatic changes and appends a redacted audit result;
- leaves the current title unchanged when native thread controls fail.

Generate the project-specific activation request with:

```bash
python3 .caps/scripts/automation-doctor.py --project . activation
```

Activate only through a Codex runtime that exposes native Scheduled controls
and native thread read/title controls. The generated request binds an absolute
prompt path and project working directory, upserts by ID, and requires native
readback. Verify with:

```bash
python3 .caps/scripts/automation-doctor.py --project . inspect
```

Never use local Codex database or global-state writes as a substitute.

## Why It Matters

Codex work gets messy when every thread is named like a diary entry. CAPS names make the action visible before you open the tab.
