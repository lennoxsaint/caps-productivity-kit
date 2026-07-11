# Setup Guide

This guide installs CAPS into an existing project.

## Prerequisites

- A project folder you can edit.
- Codex or another coding agent that reads `AGENTS.md`.
- Basic shell access.

## Install

From this kit:

```bash
./install.sh /path/to/your/project
```

The installer copies prompts, templates, docs, routing schemas, and examples
into `.caps/`.

It also writes `.caps/bootstrap/start-caps-conductor.md`, the prompt that starts
the first `CAPS CONDUCTOR` lane inside Codex.

If your project does not already have `AGENTS.md`, the installer creates one
from `templates/AGENTS.repo.md` and adds the managed CAPS lane-factory block.

If your project already has `AGENTS.md`, the installer creates a timestamped
backup and appends or updates one managed CAPS lane-factory block. Rerunning the
installer updates that block without duplicating it.

Use these flags when needed:

```bash
./install.sh /path/to/your/project --no-open
./install.sh /path/to/your/project --no-agents-update
```

`--no-open` skips opening Codex Desktop. `--no-agents-update` leaves
`AGENTS.md` untouched and installs the merge sources under `.caps/templates/`.

## Customize

Open your project `AGENTS.md` and replace every bracketed placeholder:

- Project name
- Product goal
- Install command
- Dev command
- Test command
- Build command
- Safety boundaries
- Definition of done

Do not skip the commands. Agents need exact commands or they will guess.

## Start CAPS Conductor

The installer opens Codex Desktop by default when the `codex` CLI is available.
In Codex, run:

```text
Read .caps/bootstrap/start-caps-conductor.md and execute it.
```

The bootstrap creates one project-scoped thread titled `CAPS CONDUCTOR` and pins
it when the runtime exposes safe thread-control tools. If the tools are missing,
it reports the exact skipped step and gives manual-mode copy/paste instructions.

## Add Workers

Only create worker threads when the work can be split cleanly.

Examples:

```text
BUILD LOGIN FIX
QA MOBILE NAV
RESEARCH STRIPE WEBHOOKS
REVIEW RELEASE DIFF
DOCS API QUICKSTART
```

Give each worker a prompt from `.caps/prompts/workers/` plus a narrow assignment.
When thread-control tools are available, `CAPS CONDUCTOR` can create, title, and
pin those workers after you approve the proposed lane split.

## Verify The Kit

From the CAPS kit repo:

```bash
./scripts/verify.sh
```

From your installed project, confirm:

```bash
test -f AGENTS.md
test -f .caps/bootstrap/start-caps-conductor.md
test -f .caps/prompts/conductor.md
test -f .caps/prompts/workers/implementation.md
test -f .caps/schemas/routing-decision.schema.json
```

## Upgrade Later

To update `.caps/`, rerun:

```bash
./install.sh /path/to/your/project
```

Review any local prompt edits before replacing them.
