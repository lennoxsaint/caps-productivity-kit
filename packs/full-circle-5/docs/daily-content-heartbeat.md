# Daily Content Review Heartbeat

Use this heartbeat when a student wants a daily review packet of post drafts
from their own source library.

## Purpose

At 8:00 local time, the lane prepares a daily content review packet. The packet
is for human review. It is not proof that anything was posted, scheduled, or
published.

## Required Student Inputs

- Source library or candidate run directory.
- Brand doctrine, voice notes, or style guide.
- Feedback ledger with lessons from previous posts.
- CTA, offer, and link policy.
- Approval rules for posting or scheduling.
- Local timezone.
- Scheduling tool and authentication choice.
- A prepare-only command or manual process.

## Suggested Command Shape

Adapt this to the student's own repo:

```bash
python3 tools/daily_content_review.py prepare \
  --run-dir <candidate-run-dir> \
  --date <today-local-YYYY-MM-DD> \
  --count 10 \
  --clean-count 5 \
  --cta-count 5
```

The command should prepare a review packet only. It should not post, schedule,
publish, send, or write to production databases.

## Proof Rules

Capture:

- Command run and exit status.
- Review packet path.
- Validation output.
- Exact draft posts.
- Source library or run directory used.
- Brand or feedback files read.
- Exact blockers.

Proof levels:

- Draft files prove drafts exist.
- Logs prove a process reported something.
- Queue rows prove something is queued.
- Live readback from the scheduling tool proves scheduled state.
- Public platform readback proves published state.

Do not claim live posting or scheduling from a draft packet, local log, or queue
row alone.

## Safety Rules

- No external posting without human approval.
- No external scheduling without same-day human approval.
- No direct production database writes.
- No secrets in prompts, docs, logs, or review packets.
- No private student, customer, or community data in public examples.
- No imported artifacts from another person's private content system.

## Runtime Limits

This kit can install prompts, templates, checklists, and example automation
metadata. It cannot guarantee automatic Codex thread creation, pinning, or
renaming unless the active Codex runtime exposes safe tools for those actions.
