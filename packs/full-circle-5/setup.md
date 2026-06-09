# Full Circle 5.0 Placeholder Setup

Use this pack as a generic cohort-launch shell. It can point to an approved
Full Circle-owned student OS, but it does not contain paid FC5 access, tier
gating, lesson bodies, private proof, or member data.

## Install

```bash
./install.sh /path/to/project --pack full-circle-5
```

## Before Use

Confirm the target project has its own:

- Project `AGENTS.md`.
- Real install, test, and verification commands.
- Approval gates for sends, publishing, payments, production data, and member
  communications.
- Public/private inventory for any cohort-specific material.

If FC5-specific material is needed, get it from the Full Circle owning repo or
approved gated link. Do not add it to this public CAPS shell.

## Start Mission Control

```text
Use .caps/prompts/conductor.md and .caps/packs/full-circle-5/lanes/mission-control.md.
Read AGENTS.md and the pack setup doc first.
Route only public-safe, bounded work to existing lanes.
Do not import private cohort material unless it has been classified public-safe.
```

## Runtime Limit

Shell install does not create, pin, or rename Codex threads for this pack. The
pack provides naming conventions and prompts. A CAPS Conductor may manage those
threads later when the active Codex runtime exposes safe thread-control tools.

## Daily Content Review Heartbeat

This pack includes a reusable daily content heartbeat for students.

Before enabling it, each student must provide their own:

- Source library or candidate run directory.
- Brand doctrine, voice notes, or style guide.
- Feedback ledger with lessons from prior posts.
- CTA, offer, and link policy.
- Human approval rules for posting or scheduling.
- Local timezone.
- Scheduling tool and authentication choice.
- Dry-run or review command for preparing the daily packet.

Suggested lane name:

```text
DAILY CONTENT REVIEW
```

Suggested heartbeat time:

```text
08:00 local time
```

Use:

```text
Use .caps/packs/full-circle-5/lanes/daily-content-review.md.
Prepare today's daily content review packet from my source library and brand notes.
Do not post, schedule, publish, or write to production systems.
Return exact drafts, validation output, proof paths, and blockers.
```

See:

- `.caps/packs/full-circle-5/docs/daily-content-heartbeat.md`
- `.caps/packs/full-circle-5/automation/daily-content-heartbeat.toml`
