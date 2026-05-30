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

## 4. Keep Proof

Record:

- Commands run
- Test results
- Screenshots or route proof
- PR, deploy, or release IDs
- Blockers and exact error text

## 5. Close The Loop

Before final handoff:

- Review the diff or artifact.
- Run the relevant check.
- Confirm known risks.
- Give the user the shortest useful summary.
