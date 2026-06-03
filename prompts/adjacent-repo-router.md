# Adjacent Repo Router Prompt

Use this when work may belong in a product or workflow repo instead of the CAPS
shell.

## Mission

Decide whether the requested artifact belongs in CAPS or an adjacent repo.

## Routing Rule

Keep work in CAPS only when it is:

- Generic to the CAPS operating model.
- Public-safe.
- Reusable across products or teams.
- A prompt, checklist, proof contract, install pattern, or sanitized example.

Route work to an adjacent repo when it is:

- Product-specific.
- Paid or gated.
- Dependent on private examples, proof, members, customers, or launch state.
- A live app runtime, production workflow, or account-specific integration.

## Known Adjacent Repo Roles

- Full Circle: FC5 student OS, tier packs, gated links, lesson bodies, and
  cohort operations.
- Threadify-Workflows: reusable creator-growth workflow recipes and templates.

## Output

Return:

```text
Decision: keep-in-caps | route-to-adjacent-repo | needs-owner-classification

Reason:
- ...

Public-safe CAPS artifact:
- ...

Owning repo:
- ...

Approval gates:
- ...

Proof or verification needed:
- ...
```
