# Hybrid Workers And Authority

CAPS 0.4.0 uses a hybrid worker model. The conductor owns intent, scope,
decomposition, authority, and the final proof decision. Workers execute a
bounded packet and report evidence back.

## Choose the worker kind first

Every packet declares exactly one `worker_kind`:

| Kind | Use it for | Sidebar controls |
| --- | --- | --- |
| `subagent` | Bounded work in the same task: read, analyze, test, or a disjoint reversible edit. | Never title or pin. |
| `durable_thread` | Only an explicit user request, future follow-up, separate history, host or worktree, ongoing incident, or release coordination. | Validate native controls, then title and pin if requested. |

The default is `subagent`. A durable thread is not a more powerful worker; it
is a persistence and coordination choice. Do not create one merely because a
lane sounds important, because the conductor is busy, or because a prompt is
long.

When the current user request already permits local, reversible work, the
conductor may delegate a qualifying subtask automatically. It does not ask for
per-worker approval. Native subagent control uses `spawn_agent`, `list_agents`,
`send_message`, `followup_task`, `wait_agent`, and `interrupt_agent`. Creating a
`durable_thread` is different: it always requires an explicit user request and
uses the separate thread-control surface.

## Packet contract

Use [`templates/worker-packet.md`](../templates/worker-packet.md) for each
worker. The packet must state:

- `worker_kind`, exact model, thinking level, and `fork_turns`;
- a redacted task snapshot, acceptance gate, risk, and stop conditions;
- the one write owner and exact file set, or `inspect-only`/`test-only`;
- allowed local actions and prohibited external or authority-changing actions;
- capability checks, delegation depth, receipt mode, and the final output shape.

For a mixed-model packet, set `fork_turns: none` by default. A bounded positive
value may inherit only the needed recent turns and may still carry an explicit
model and thinking override. `fork_turns: all` inherits the parent model and
thinking and cannot accept an override. It is therefore not a mixed-model
route. No fork mode overrides the packet's worker kind, authority, or file set.
If the runtime cannot honor the requested capabilities, stop and report the
exact gap; do not silently substitute.

## Authority and write ownership

One worker owns writes for one declared file set. Other workers may inspect,
analyze, or test that set but must not edit it. Disjoint reversible edits are
allowed when their file sets do not overlap and each packet names its owner.
The conductor resolves conflicts; workers do not widen ownership, scope, or
authority on their own.

Local read, analysis, test, and reversible disjoint edits may proceed when the
packet allows them. The default prohibition list is:

- external sends or posts;
- production data writes, payments, or account changes;
- merge, deploy, publish, or release execution;
- credential, secret, permission, or authentication changes;
- destructive or irreversible actions;
- authority widening or delegation outside the packet.

Stop and report before any prohibited action, even if a tool makes it easy.

## Fan-out and delegation

Start with at most four workers. Scale to at most ten only for independent,
deterministic, non-colliding lanes with separate owners and file sets. Keep
tightly coupled work in the conductor. Workers cannot delegate by default;
the packet must explicitly allow it, and nested delegation may not exceed depth
two. Ultra is root-only and may not be assigned to a worker or nested worker.

## Capability and receipt gates

Build the capability snapshot with `scripts/capability-snapshot.py` from a
catalog read directly from the live Codex runtime or App Server model catalog.
The catalog must identify that runtime source and the current capture time.
Treat a hand-maintained model list, a copied example, the screenshot of another
runtime, or a stale snapshot as documentation, not capability truth. Refresh
the runtime catalog immediately before a routed run whenever its freshness is
unknown or outside the task's declared freshness window.

Before execution, validate the requested model, thinking level, worker kind,
`fork_turns`, and (for durable threads) title/pin controls against that fresh
snapshot. Record unavailable capabilities exactly. A failed or missing receipt
is degraded observability, not proof of success. A degraded receipt may report
only what was observed and must preserve the normal quality gate and stop
conditions.

Every receipt follows one atomic lifecycle: start it with the capability
snapshot digest immediately before spawning, bind the returned worker reference
immediately after a successful spawn, then finish or abandon it after review.
A spawn failure closes the pending receipt as abandoned; it never leaves a
phantom worker or invents an outcome.

Receipts are public-safe metadata: route, worker kind, outcome, proof labels,
and short blocker labels. Never place raw prompts, answers, secrets, customer
data, private paths, or private thread IDs in a public receipt.

## Public and private surfaces

The public kit contains generic policy, placeholders, and sanitized examples.
A private profile may add local history, tools, paths, host/worktree details,
or evidence references. Keep those details in the private profile and pass only
the smallest redacted packet needed for the worker. Public documentation must
not imply access to a private runtime, account, connector, or live surface.

## Title sync and updater rollout

Pinned-title sync and stable updater automations are distributed as paused
proposals. Copying a proposal is not activation. The conductor must require
native schedule/thread controls and read back the saved model, reasoning,
target, prompt path, status, and scope before calling either automation active.
If controls or readback are unavailable, leave the proposal paused and report
`degraded observability` or the exact blocker. Do not use local state files as a
substitute.

## Worker completion

A worker reports `done`, `blocked`, or `needs review` with files, commands,
proof labels, skipped checks, and next gate. A local result proves only that
local result. Titles, pins, receipts, and logs are coordination metadata; they
do not prove a send, publish, merge, deploy, release, or live outcome.
