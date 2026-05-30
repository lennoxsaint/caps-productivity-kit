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

The installer copies prompts, templates, docs, and examples into `.caps/`.

If your project does not already have `AGENTS.md`, the installer creates one from `templates/AGENTS.repo.md`.

If your project already has `AGENTS.md`, the installer leaves it alone and places the template at `.caps/templates/AGENTS.repo.md` for manual merging.

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

## Start A Conductor Thread

In Codex, start a new thread:

```text
Use .caps/prompts/conductor.md as the operating prompt for this workspace.
Read AGENTS.md first, then help me plan and execute the next project slice.
```

Name it with the convention in `.caps/docs/naming-and-pinning.md`.

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

## Verify The Kit

From the CAPS kit repo:

```bash
./scripts/verify.sh
```

From your installed project, confirm:

```bash
test -f AGENTS.md
test -f .caps/prompts/conductor.md
test -f .caps/prompts/workers/implementation.md
```

## Upgrade Later

To update `.caps/`, rerun:

```bash
./install.sh /path/to/your/project
```

Review any local prompt edits before replacing them.
