# Conductor Workflow

The conductor is the main project brain for a task or release.

## 1. Read The Room

Start by reading:

- `AGENTS.md`
- Relevant README/docs
- Current git status
- Files directly tied to the request
- Recent logs or errors when debugging

## 2. Define Done

For substantial work, state:

- Goal
- Constraints
- Risks
- Done means

Example:

```text
Goal: Add password reset to the app.
Constraints: Keep existing auth provider, no production secret changes.
Risks: Email delivery and token expiry.
Done means: User can request reset, receive link in dev, set new password, and tests pass.
```

## 3. Split Only When Useful

Use workers for independent lanes:

- Research a provider behavior while the conductor inspects code.
- QA a local build while implementation continues in a separate branch.
- Review a completed diff before merge.
- Draft docs while tests run.

Do not create workers for tiny tasks. Coordination has a cost.

For every real worker packet, choose `worker_kind`, the GPT-5.6 route, and
authority envelope before creating it. See `docs/gpt-5-6-routing.md`; the
decision must conform to `schemas/routing-decision.schema.json`. Pass exact
`model`, `thinking`, and `fork_turns` values to the requested worker kind. Only
a validated `durable_thread` may be titled and pinned. A native `subagent` is
same-task work and is never titled or pinned. The authority envelope is an
action-time guardrail: it names what the worker may do, may not do, must prove,
and must stop for.

Complete the decision's redacted task snapshot before routing. The conductor
owns task understanding, decomposition, risk, acceptance criteria, and stop
conditions; the worker receives that bounded packet instead of reconstructing
intent from a raw brain dump or voice transcript.

Optimize verified successful work per minute through that proof gate. Count
failed probes, retries, and rework. Use Luna for safe deterministic probes,
Terra only with repeated personal/runtime evidence, and Sol when ambiguity or
failure cost makes probing wasteful. Ultra is a root-only topology and must not
be assigned to an already delegated worker.

For complex, proof-sensitive, or multi-surface work, first decide whether the
task needs a dynamic harness. A harness is a temporary task organization with
explicit evidence sources, split roles, verifier rubrics, stop conditions, and
proof-state targets. See `docs/dynamic-harnesses.md`.

Route to existing active durable lanes before creating new ones. A pinned worker
thread should own a bounded outcome, not a vague topic. If an existing lane already owns
the repo, product area, or proof path, continue that lane instead of starting a
duplicate.

When the active Codex runtime exposes safe thread-control tools, the conductor
may create approved durable worker lanes directly after the user approves the split:

- Use `create_thread` for the worker.
- Immediately call `set_thread_title` and `set_thread_pinned` only for a
  validated `durable_thread` returned by `create_thread`.
- Use action-first uppercase titles capped at 48 characters.
- Report the thread id, title status, and pin status.

If those tools are unavailable, continue in manual mode for durable threads.
Give the user the worker title and copy/paste prompt, and name the exact
skipped tool step. Do not title or pin a subagent.

Do not mutate Codex state files directly.

New lanes need:

- A clear outcome.
- The right workspace or repo.
- A stop condition.
- An evidence contract.
- An unpin rule (or `not applicable` for a subagent).

Every routed prompt must carry enough context for a cold worker thread. Include:

- Source conductor thread and reason for routing.
- The decision already made by the conductor.
- Relevant conversation summary.
- Target workspace and key files or live surfaces.
- What is public-safe, private/local-only, or approval-gated.
- What not to redo.
- Exact outcome, output format, proof standard, and stop condition.
- Whether the worker may edit files, inspect only, or return a plan.

This applies when continuing existing threads and when creating new threads.
Existing workers are not guaranteed to remember the conductor's latest reasoning.
If the worker needs the context to avoid a bad assumption, put that context in
the routed prompt.

When the conductor is in a hold state, do not create new threads unless the user
explicitly asks for that. Keep routing, status, and proof work inside the
existing pinned lanes.

## 4. Show The Lane Tree

When a brain dump becomes multiple lanes, show a compact tree before or
alongside the lane list so the user can see how work is being separated.

Default to Mermaid `flowchart TD` for normal conductor output. Use SCDiagram
when the workspace supports it and the split needs richer system/context
notation. Use a native image jam only when a rendered planning artifact would
help the user review the split.

The tree should show:

- The brain dump or request.
- The conductor/router.
- Existing lanes reused first.
- Any proposed new lanes.
- Waiting-on, proof, and unpin gates where useful.

Do not delay routing on image generation. If the surface cannot render the
diagram, provide the fenced Mermaid/SCDiagram source and a plain text outline.
Keep secrets, private member data, account IDs, private proof paths, and
credentials out of the diagram.

## 5. Keep Proof

Record:

- Commands run
- Test results
- Screenshots or route proof
- PR, deploy, or release IDs
- Blockers and exact error text

Morning backfeed should name:

- Active lanes
- Blockers
- Highest-leverage next action
- Unpin candidates
- What the operator loop found since the last report

Evening backfeed should name:

- Shipped work
- Slipped work
- Still-active lanes
- Waiting on the user
- Waiting on tools or proof
- Proof states that changed

For cross-surface triage, use `docs/operator-loop.md`. Start read-only, label
proof states, and stop before external sends, publishing, payments, destructive
actions, production writes, merges, or deploys unless the current project
instructions and latest user request clearly authorize them.

## 6. Close The Loop

Before final handoff:

- Review the diff or artifact.
- Run the relevant check.
- Confirm known risks.
- Give the user the shortest useful summary.
