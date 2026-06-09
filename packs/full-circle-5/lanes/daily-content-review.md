# Lane: Daily Content Review

Use this as the pinned daily content lane for a student-owned content workflow.

## Objective

Prepare a daily review packet from the student's own source library, brand
notes, feedback ledger, and CTA policy.

## Default Cadence

Run around 8:00 local time.

The pack can provide a heartbeat template. Shell install does not create, title,
or pin this lane. A CAPS Conductor may do that later when the active Codex
runtime exposes safe tools for those actions.

## Required Inputs

- Source library or candidate run directory.
- Brand doctrine, voice notes, or style guide.
- Feedback ledger.
- CTA, offer, and link policy.
- Approval rules.
- Timezone.
- Scheduling tool and authentication choice.
- Prepare-only command or manual review process.

## Work Rules

- Prepare drafts for review.
- Include exact draft text in the packet.
- Validate the packet with the student's repo-owned checks when available.
- Keep the lane in draft/review mode by default.
- Do not post, schedule, publish, send, or write production data.
- Do not use another person's private examples, artifacts, thread IDs, or
  account details.

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

## Proof Contract

Return:

- Date and timezone.
- Source library or run directory used.
- Brand notes and feedback ledger used.
- Command run and exit status.
- Review packet path.
- Validation output.
- Exact draft posts.
- Approval status.
- Live readback, only if human-approved scheduling was performed.
- Exact blockers.

## Stop Conditions

Stop before external action if:

- Human approval is missing.
- Scheduling or publishing credentials are missing.
- The command would write directly to production data.
- Private data appears in the review packet.
- The scheduling tool cannot provide live readback.

## Output

Return:

```text
Status: prepared | blocked | approved-scheduled

Date/timezone:
- ...

Inputs:
- ...

Drafts:
- ...

Verified:
- ...

Approval:
- ...

Blocked:
- ...

public_repo_sync_recommendation: yes/no
```
