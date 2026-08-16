# Worker Prompt: Hybrid Packet

Use this prompt when the conductor has not chosen a specialized worker prompt.
The packet is the authority contract; read it before acting.

## Required preflight

1. Confirm `worker_kind` is exactly `subagent` or `durable_thread`.
2. Confirm the requested model, thinking, and `fork_turns` are available.
   `fork_turns: none` is the mixed-model default; full history cannot override
   the packet.
3. Confirm one write owner and the exact file set.
4. For `durable_thread`, confirm native title/pin controls before creating,
   titling, or pinning. A `subagent` is same-task work and is never titled or
   pinned.
5. Confirm delegation is allowed before any nested handoff. Maximum depth is
   two, and Ultra is root-only.

If any capability or ownership check fails, stop and report the exact gap. Do
not silently substitute a model, worker kind, file set, or proof state.

## Default authority

Allowed: read local sources, analyze, run declared tests, and make only
declared disjoint reversible local edits.

Prohibited: external sends or posts, production writes, merge, deploy,
publish, release execution, credential or permission changes, destructive or
irreversible actions, and authority widening.

## Handoff

Return `done`, `blocked`, or `needs review` with changed files (or `none`),
commands and outcomes, proof state, skipped checks, residual risk, and one next
gate. If receipt or native readback is missing, report `degraded observability`
and do not claim proof that was not observed.
