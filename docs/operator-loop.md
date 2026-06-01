# Operator Loop

CAPS works best when the conductor can answer one practical question:

```text
What did I miss?
```

This is not a request for an agent to take over. It is a read-first workflow for
finding the few things that need human attention across project lanes, inboxes,
calendars, docs, and proof logs.

## Default Mode

Start read-only.

The operator may:

- Read approved project files, docs, queues, calendars, inbox summaries, and
  local logs.
- Summarize urgent replies, stale asks, blockers, and missing proof.
- Draft suggested next actions.
- Label approval gates.

The operator must not:

- Send messages.
- Publish content.
- Schedule external posts.
- Pay, buy, sign, delete, merge, deploy, or change production data.
- Claim live proof from a draft, queue row, or log line.

## Connector Hierarchy

Prefer tool surfaces in this order:

1. Official API or CLI returning structured output.
2. Local text files, Markdown, CSV, SQLite, and repo artifacts.
3. Browser automation with authenticated profile proof.
4. Screen automation as the final fallback.

If a connector is missing auth, permissions, or account setup, label that exact
gate. Do not pretend the surface was scanned.

## What To Report

Return:

- Urgent human replies or decisions.
- Waiting-on-user gates.
- Waiting-on-tool or waiting-on-proof gates.
- Stale active lanes.
- Draft, queued, scheduled, sent, published, deployed, or live-verified status.
- Suggested first next action.
- Connector gaps.
- Mistakes that should become durable instructions.

## Control Action Proof State

Use this matrix before claiming completion:

| State | Meaning | Proof |
| --- | --- | --- |
| read | Source inspected without changing it. | Source path, API/CLI readback, or screenshot timestamp. |
| draft | Proposed output exists but has not been sent or applied. | Draft path, diff, or quoted summary. |
| queued | Work is staged in a local or platform queue. | Queue row, manifest, or draft ID. |
| scheduled | A platform accepted a future action. | Platform readback with account, time, and payload summary. |
| sent | A message was sent. | Sent-mail/chat readback with recipients and timestamp. |
| published | External audience can see it. | Public or member-facing readback. |
| merged | Code entered a shared branch. | Commit/PR readback and checks. |
| deployed | Build reached an environment. | Deploy receipt and version/URL. |
| live-verified | Real target surface proves the intended effect. | Browser/API/device/customer-facing proof. |
| blocked | A named gate prevents progress. | Exact blocker, attempted alternatives, and next owner. |

## Approval Bands

| Band | Examples | Default behavior |
| --- | --- | --- |
| Low | Read, summarize, local draft. | Proceed with source refs. |
| Medium | Local edits, recoverable archive, safe fixture writes. | Proceed when the task implies it; keep recovery path. |
| High | External sends, scheduling, production writes, deploys, merges. | Proceed only when authority is clear and proof is captured. |
| Hard stop | Payments, destructive deletes, secrets, irreversible actions. | Require explicit approval or report blocked. |

## Report Template

```text
Status: read | draft | queued | scheduled | sent | published | live-verified | blocked

Attention:
- ...

Waiting on user:
- ...

Waiting on tool/proof:
- ...

First next action:
- ...

Connector gaps:
- ...

Skill or instruction updates:
- ...
```
