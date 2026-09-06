# Dynamic Harnesses

A dynamic harness is a temporary task organization for work that is too messy,
proof-sensitive, or multi-surface for one long chat.

Use a harness to decide:

- Which evidence sources matter.
- Which work can be split safely.
- Which reviewer should challenge the result.
- Which proof state counts as done.
- Which actions are blocked until human approval.

Do not use a harness for simple commands, one-file edits, or obvious direct
execution. Coordination has a cost.

Harness fan-out follows the hybrid worker contract. Start with at most three concurrent
workers. Larger teams require an explicit owner request and remain limited to
ten independent, deterministic,
non-colliding roles with separate write owners and file sets. Same-task roles
are native subagents and are never titled or pinned. Durable threads require a
qualifying persistence reason and validated native controls. Workers cannot
delegate unless an explicit owner request is recorded in the packet, with nested depth capped at
two.

## When To Use One

Use a harness when at least two are true:

- The work spans multiple repos, tools, products, or proof sources.
- A false "done" claim would be expensive.
- Independent review would catch real risk.
- The task has many items to classify, rank, verify, compare, or dedupe.
- The task may drift across a long run or after context compaction.
- The user explicitly asks for delegation, subagents, a workflow, an audit, a
  tournament, or a multi-pass review.

## Common Patterns

- `classify-and-act`: route items by type, owner, risk, or proof state.
- `fan-out-and-synthesize`: inspect independent slices, then merge findings.
- `adversarial-verification`: challenge claims against evidence and a rubric.
- `generate-and-filter`: create options, dedupe them, score them, keep the best.
- `tournament`: compare competing approaches against the same rubric.
- `loop-until-done`: continue until no new findings, no failing checks, or a
  named stop condition.

## Harness Template

```yaml
harness:
  name: "..."
  use_harness: yes/no
  eligibility_reason: "..."
  objective: "..."
  success_gate: "..."
  proof_state_target: "draft|queued|scheduled|sent|published|merged|deployed|live-verified|blocked"
  source_truth:
    - "..."
  patterns:
    - "classify-and-act|fan-out-and-synthesize|adversarial-verification|generate-and-filter|tournament|loop-until-done"
  roles:
    - name: "..."
      purpose: "..."
      inputs: ["..."]
      output: "..."
      allowed_actions: "inspect-only|local-edit|test-only|draft-only"
      forbidden_actions:
        - "send"
        - "schedule"
        - "publish"
        - "merge"
        - "deploy"
        - "production-write"
        - "secrets"
        - "destructive-action"
  verifier_required: yes/no
  verifier_rubric:
    - "..."
  token_or_time_budget: "..."
  stop_condition: "..."
  recovery_path: "..."
  final_output_contract:
    - "..."
```

## Verifier Rubric

Before calling a harnessed task done, ask:

- Does the evidence prove the claimed proof state?
- Are drafts, queue rows, logs, screenshots, dashboards, and live readbacks kept
  separate?
- Are external actions and approval gates named?
- Are source paths, commands, checks, and skipped actions recorded?
- Is the next action small, safe, and reversible where practical?

## Safe Public Examples

Good public-safe examples:

- "Verify every technical claim in this blog post against the repo."
- "Rank 80 customer notes against this rubric and double-check the top 10."
- "Find recurring incident causes from six months of logs and propose tickets."
- "Compare three implementation approaches and pick the lowest-risk one."

Unsafe examples for a public kit:

- Private thread IDs.
- Customer or member names.
- Account handles or secrets.
- Internal launch gates.
- Private screenshots or proof paths.
- Paid lesson bodies or unreleased product claims.

## Stop Conditions

Stop before:

- Sending messages.
- Scheduling or publishing external content.
- Merging, deploying, or pushing shared branches.
- Writing production data.
- Changing secrets, billing, payments, or account settings.
- Running destructive filesystem or git operations.

Report the exact blocked action, the evidence gathered, and the next approval
or proof gate.
