# CAPS Authority Envelope

Use this short envelope inside every worker packet. Keep it specific enough
that a cold worker can act without guessing.

```yaml
authority:
  allowed:
    - "read declared local sources"
    - "analyze evidence and run declared tests"
    - "make reversible local edits only within the declared file set"
  prohibited:
    - "external sends, posts, or messages"
    - "production writes, payments, or customer/account changes"
    - "merge, deploy, publish, or release execution"
    - "credentials, secrets, permissions, or authentication changes"
    - "destructive or irreversible actions"
    - "authority, scope, owner, or file-set widening"
  proof_required:
    - "files changed or an explicit none"
    - "commands and outcomes"
    - "proof state that matches the claim"
  stop_conditions:
    - "required capability is unavailable"
    - "scope, ownership, or authority is ambiguous"
    - "a prohibited action would be needed"
    - "evidence cannot satisfy the acceptance gate"
```

The conductor may narrow this envelope. It must not be widened by a worker.
