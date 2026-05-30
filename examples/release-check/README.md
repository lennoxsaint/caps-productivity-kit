# Example: Release Check

Use this when a change is built and needs release confidence.

## Conductor Start

```text
Use .caps/prompts/conductor.md.
Goal: Verify release candidate v1.4.0 before production deploy.
Done means: tests pass, changelog is accurate, rollback is known, and live smoke checks are listed.
```

## Worker: Review

```text
Use .caps/prompts/workers/review.md.

Objective: Review the release diff for user-impacting regressions.
Compare:
- main...release/v1.4.0

Focus:
- Auth
- Billing
- Data migrations
- API compatibility

Do not edit files. Return findings only.
```

## Worker: QA

```text
Use .caps/prompts/workers/qa.md.

Objective: Run release smoke checks.
Commands:
- npm test
- npm run build

Manual checks:
- Login
- Core happy path
- Billing page loads
- Settings save
```

## Release Handoff

```text
Status: needs review

Verified:
- npm test passed.
- npm run build passed.
- Login and settings smoke checks passed.

Risk:
- Billing page loads but webhook delivery was not tested locally.

Next:
- Deploy to staging and verify webhook receipt before production.
```
