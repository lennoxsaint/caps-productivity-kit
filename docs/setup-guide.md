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

Use native `subagent` workers for bounded same-task work. They are not sidebar
lanes and must never be titled or pinned. Create a `durable_thread` only for an
explicit user request, future follow-up, separate history, host or worktree,
ongoing incident, or release coordination.

Within the authority already granted by the current request, the conductor can
delegate safe local subagent work automatically; it does not pause for approval
for each worker. The native controls are `spawn_agent`, `list_agents`,
`send_message`, `followup_task`, `wait_agent`, and `interrupt_agent`. Durable
thread creation remains explicit-user-only.

Examples:

```text
BUILD LOGIN FIX
QA MOBILE NAV
RESEARCH STRIPE WEBHOOKS
REVIEW RELEASE DIFF
DOCS API QUICKSTART
```

Give each worker a packet from `.caps/templates/worker-packet.md` and a prompt
from `.caps/prompts/workers/` plus a narrow assignment. Each packet names one
write owner and exact file set. Validate model, thinking, worker kind, and
`fork_turns` before execution; never silently substitute a capability.

Start with at most four workers. Scale to at most ten only for independent,
deterministic, non-colliding lanes. Workers cannot delegate by default;
explicit nested delegation stops at depth two, and Ultra is root-only.

When native thread-control tools are available, `CAPS CONDUCTOR` can create,
title, and pin only a validated durable thread after the user explicitly asks
for it. For mixed-model packets, use `fork_turns: none` by default; a bounded
positive fork may also use an explicit override. `fork_turns: all` inherits the
parent model and thinking and cannot accept an override.

Before routing, export the live Codex runtime or App Server model catalog with
its source and capture time, then build the digest-bearing snapshot with
`.caps/scripts/capability-snapshot.py`. Do not use a manual model list, example,
screenshot, or stale snapshot as live availability truth.

See [`hybrid-workers.md`](hybrid-workers.md) for the authority and receipt
contract.

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
test -f .caps/prompts/workers/hybrid.md
test -f .caps/templates/worker-packet.md
test -f .caps/templates/authority-envelope.md
test -f .caps/schemas/routing-decision.schema.json
test -f .caps/scripts/capability-snapshot.py
test -f .caps/scripts/caps-update.py
test -f .caps/scripts/automation-doctor.py
test -f .caps/automations/pinned-title-sync/automation.toml
```

Also review the installed public-safe contract:

```bash
test -f .caps/docs/hybrid-workers.md
rg -n "worker_kind|subagent|durable_thread|fork_turns|write owner" \
  .caps/docs/hybrid-workers.md .caps/templates/worker-packet.md
```

These checks confirm documentation and packet surfaces exist; they do not
prove a worker ran, a thread was created, or an automation is active.

## Activate Scheduled Tasks

The installer copies proposals; it does not claim they are registered. Generate
the exact project-specific activation request:

```bash
python3 .caps/scripts/automation-doctor.py --project . activation
```

Give the output to Codex in a runtime with native Scheduled task controls. It
will request an idempotent upsert for both tasks, use absolute prompt paths,
bind the current project working directory, and require a native readback.
CAPS never substitutes direct edits to Codex registry files.

After activation, verify the real registry state:

```bash
python3 .caps/scripts/automation-doctor.py --project . inspect
```

The command exits non-zero with `registration_required`, `template_invalid`, or
`drift` until both tasks are natively active and match their project, schedule,
model, reasoning effort, and prompt path.

## Upgrade Later

Version 0.3.0 and later records managed-file hashes and supports the stable
update channel:

```bash
python3 .caps/scripts/caps-update.py --project . check
python3 .caps/scripts/caps-update.py --project . apply
```

The updater verifies the release digest and compatibility, preserves local
configuration, state, and modified managed files, and creates a rollback
backup. Older installations need one final rerun of the current `install.sh` to
install the update foundation; review local prompt changes first.
