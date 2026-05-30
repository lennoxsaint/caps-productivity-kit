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

Route to existing active lanes before creating new ones. A pinned worker thread
should own a bounded outcome, not a vague topic. If an existing lane already owns
the repo, product area, or proof path, continue that lane instead of starting a
duplicate.

New lanes need:

- A clear outcome.
- The right workspace or repo.
- A stop condition.
- An evidence contract.
- An unpin rule.

When the conductor is in a hold state, do not create new threads unless the user
explicitly asks for that. Keep routing, status, and proof work inside the
existing pinned lanes.

## 4. Keep Proof

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

Evening backfeed should name:

- Shipped work
- Slipped work
- Still-active lanes
- Waiting on the user
- Waiting on tools or proof

## 5. Close The Loop

Before final handoff:

- Review the diff or artifact.
- Run the relevant check.
- Confirm known risks.
- Give the user the shortest useful summary.
