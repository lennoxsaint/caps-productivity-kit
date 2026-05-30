# Evidence And Handoffs

CAPS is useful only if work can be trusted after the thread closes.

## Evidence To Capture

For code:

- Files changed
- Tests run
- Build or typecheck result
- Known skipped checks

For UI:

- Desktop proof
- Mobile proof
- Console status
- Screenshots when available

For releases:

- Commit SHA
- PR link
- Deploy ID
- Live route proof
- Rollback path

For research:

- Source links
- Date checked
- Confidence level
- Inferences separated from facts

## Handoff Format

Use this:

```text
Status: done | blocked | needs review

Changed:
- ...

Verified:
- ...

Risk:
- ...

Next:
- ...
```

## Blocker Format

Use exact blockers:

```text
Blocked by: missing STRIPE_SECRET_KEY in local environment.
Tried: checked .env.example, project docs, and deployment config names.
Next gate: user or maintainer provides credential through the approved secret manager.
```

Never turn a local draft, queue row, or log line into a claim of live success.
