# CAPS Glossary

## Hybrid worker model

CAPS 0.4.0 supports two worker kinds: `subagent` and `durable_thread`. A
`subagent` is native, bounded same-task work. It is not a sidebar lane and is
never titled or pinned. A `durable_thread` is a separately addressable lane
kept for an explicit user request, future follow-up, separate history, host or
worktree, an ongoing incident, or release coordination.

## Routing decision

A machine-readable record that selects the GPT-5.6 model and thinking level for
one worker lane, explains the choice, and includes its authority envelope.

## Operational route

The GPT-5.6 worker route that can perform the assigned lane within its authority
envelope and proof requirements.

## Worker packet

A conductor-owned, public-safe task packet containing `worker_kind`, a redacted
task snapshot, exact model and thinking values, `fork_turns`, the write owner
and file set, capability requirements, authority envelope, proof contract, and
stop conditions. A packet is sufficient for a cold worker and never forwards
raw conversation history by default.

## Write owner and file set

The one worker authorized to make edits and the exact files or surfaces it may
edit. Other workers are read-only or test-only for that set. A worker may not
silently widen either the owner or the file set.

## Advisory fallback

A narrow, non-executing planner, reviewer, or council exception. It requires a
specific reason and never replaces the GPT-5.6 operational worker.

## Authority envelope

The action-time guardrail for a worker: allowed actions, prohibited actions,
required proof, and stop conditions.

Automatic local reads, analysis, tests, and disjoint reversible edits are
allowed when listed in the packet. External sends, production writes,
merges, deploys, publishes, credential changes, irreversible actions, and
authority widening are prohibited unless a separate current authority gate
explicitly permits them.

## Escalation

The stated condition that requires the worker to stop, report evidence, or ask
the conductor to reroute or expand authority.

## Delegation depth

The number of nested worker handoffs below the conductor. Workers cannot
delegate by default. A packet must explicitly allow nested delegation, and the
maximum depth is two. Ultra is root-only.

## Task state snapshot

A redacted conductor-owned description of the objective, scope, acceptance
criteria, risk, side effects, evidence references, and stop conditions that is
complete enough to route a worker without forwarding raw conversation history.

## Capability validation

A preflight check that the runtime supports the requested worker kind, model,
thinking level, `fork_turns`, and (for durable threads) native title/pin
controls. Missing capabilities are reported as unavailable; CAPS never
silently substitutes a different model, worker kind, or proof state.

## Title coordination metadata

A pinned-thread label that helps the user find current work. It can describe
the evidence-supported task state, but it never proves execution or completion.
Only durable threads may receive a title or pin. Subagents remain untitled and
unpinned even when they produce a receipt.

## Manual title override

An owner-selected title or emoji that automatic title synchronization preserves
until the owner changes or clears it.

## Update channel

A named stream of versioned CAPS release manifests. Each manifest declares the
artifact digest, compatibility range, disruption state, release notes, and
rollback version.

## Degraded receipt

A local, redacted record that observability was incomplete or unavailable. It
may say that a worker was started, finished, blocked, or unobserved, but it
never upgrades a draft, local test, or missing readback into completion proof.

## Public/private separation

The public kit contains portable rules, placeholders, and sanitized examples.
Private profiles may add local routes, history, tools, paths, and evidence, but
must not be copied into public packets or receipts.
