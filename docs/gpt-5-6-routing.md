# Astra and Mixed-Model Routing

CAPS 0.5.0 routes worker work for verified successful work per minute, including
retries and rework through the acceptance gate. Keep quick answers,
clarifications, and tightly coupled work in the conductor. Create a worker only
for an independent deliverable or proof lane.

The conductor preserves the user's selected model and reasoning effort. This
worker policy does not change either setting. The filename is retained for
upgrade compatibility with existing CAPS installations.

Evidence basis: the [OpenAI model guide](https://learn.chatgpt.com/docs/models)
positions Astra for demanding end-to-end work, Sol for complex bounded work,
Terra for everyday reasoning and tools, and Luna for clear repeatable tasks.
Model roles are starting hypotheses; real task receipts govern promotion.
Check current official pricing and live account capabilities before making
cost or availability claims. No historical price or benchmark sets a route.

## Hybrid worker packet

Every routed worker declares `worker_kind: subagent | durable_thread`. Use a
native `subagent` for bounded same-task work; it is never titled or pinned. Use
`durable_thread` only for an explicit user request, future follow-up, separate
history, host or worktree, ongoing incident, or release coordination. Start
with at most three concurrent workers. Larger teams require an explicit owner
request and remain limited to ten independent,
deterministic, non-colliding lanes.

When the parent request authorizes local reversible work, the conductor may
automatically delegate an independent subtask through `spawn_agent`, observe it
with `list_agents`, coordinate it with `send_message` or `followup_task`, await
it with `wait_agent`, and stop it with `interrupt_agent`. This automatic path
does not require per-subagent approval. It never authorizes creation of a
durable thread; `durable_thread` remains explicit-user-only.

Every packet names one write owner and exact file set. Local reads, analysis,
tests, and disjoint reversible edits may be allowed. External sends,
production writes, merge, deploy, publish, credential changes, irreversible
actions, and authority widening are prohibited by default. Workers cannot
delegate by default; owner-requested nested delegation stops at depth two. Ultra is
root-only.

For mixed-model packets, `fork_turns: none` is the default. Use a bounded
positive value only when the packet explains why inherited context is needed;
both modes may specify an explicit model and thinking override. `fork_turns: all`
inherits the parent model and thinking and cannot accept an override, so it
is not a mixed-model route. No fork mode changes the packet's worker kind,
authority, or file set.

Validate model, thinking, worker kind, `fork_turns`, and (for durable threads)
native title/pin controls before execution. Missing capabilities are reported;
never silently substitute a route or proof state.

## Conductor-first task understanding

Before selecting a worker route, the Brain Conductor creates the routing
decision's `task_snapshot`. A Voice Conductor supplies the same fields rather
than forwarding a raw transcript. The snapshot locks:

- the outcome and bounded scope;
- acceptance criteria and evidence already available;
- failure and side-effect risk;
- stop conditions and owner decisions.

Do not delegate until the snapshot is complete. A worker receives the snapshot,
authority envelope, quality gate, and escalation route as one self-contained
packet. This keeps cheap workers bounded and lets the conductor retain
ambiguity, prioritization, and cross-lane judgment.

The model capability snapshot is a separate live-runtime input. Export the
current Codex runtime or App Server model catalog, including its provenance and
capture time, then pass it through `scripts/capability-snapshot.py`. Validate
every explicit model and reasoning level against its digest. Never promote a
manual list, sanitized example, screenshot, or stale prior snapshot into live
capability truth; refresh it when provenance or freshness cannot be established.

## Worker Matrix

| Work shape | Model | Thinking |
| --- | --- | --- |
| Extraction, classification, transformation, indexing, repeatable structured summaries | `gpt-5.6-luna` | `low` |
| Mechanical frozen-plan implementation with deterministic tests and safe retry | `gpt-5.6-luna` | `high` |
| Bounded tool work where repeated personal/runtime evidence shows Luna loses and Sol adds no value | `gpt-5.6-terra` | evaluated effort |
| Integration-sensitive implementation or multi-step work needing judgment | `gpt-5.6-sol` | `medium` |
| Ambiguous architecture, deep research, incidents, consequential strategy, computer use, polished high-value deliverables | `gpt-5.6-sol` | `high` or `xhigh` |
| Demanding end-to-end work across code, apps, and research | `gpt-6-astra` | `high` or `xhigh` |
| Rare, indivisible hardest problem | `gpt-6-astra` | `max` |
| Rare, high-value task with multiple genuinely independent workstreams, root only | selected capable model | supported `ultra` |

Terra is not a guaranteed middle lane. It is an evidence-gated exception: use
it only when repeated personal evals or runtime receipts show better verified
completions per minute than passing Luna and Sol candidates for that work shape.
A bounded Terra trial is also allowed before promotion: use `trial` with
`deterministic_verification: true` and `safe_retry: true`, a low/medium-risk
coding, transformation, or proof-review task, local-reversible authority, and
`probe_then_escalate` with an eligible Sol/Astra fallback. A trial does not
waive the promotion gate or establish that Terra is better.
An aggregate intelligence-versus-cost benchmark may motivate a candidate set,
but it cannot promote or eliminate a route by itself because task-specific tool
use, retries, latency, and failure cost are outside a single aggregate score.

Max and Ultra are reasoning levels, not model IDs. Use Max only when the problem
cannot be safely split. Use Ultra only when the workstreams are genuinely
independent and their coordination has high value. Neither is a default for
urgency or a vague request. Ultra is root-only: never assign it to an already
delegated worker or create nested Ultra delegation.

## Quality-Gated Cascade

1. Define the quality gate and cost of failure before choosing a model.
2. Start with the least expensive route expected to pass. Luna is appropriate
   only when the task is precise, safely retryable, and deterministically verified.
3. Outside bounded trials, use Terra only when `personal_eval` or `runtime_observation` shows it beats
   both the passing Luna route and the relevant Sol route on verified successful
   work per minute.
4. Use Sol for complex bounded work and Astra for demanding end-to-end work
   when a cheap probe would add waste or failure risk.
5. Escalate after one observable quality failure or material scope expansion.
   Count every attempt in elapsed time and usage; do not hide failed probes.
6. Escalate immediately when the task snapshot proves incomplete, the worker
   weakens acceptance criteria, or an unexpected side effect appears. Do not
   repeat the same failed route with more effort and call it a new strategy.

Treat a synthetic fixture winner as provisional evidence, not permanent truth.
Recalibrate after 30 real task receipts or 30 days, whichever comes first.

## Closed-loop calibration

CAPS records redacted lifecycle receipts in
`~/.codex/routing/receipts.jsonl` by default. A receipt contains route metadata,
elapsed and rework time, pass/fail state, retry count, token/cost diagnostics
when available, snapshot completeness, delegation quality, gate result,
escalation reason, and short proof labels. It must not contain raw task text,
answers, secrets, customer data, or private proof content.

Start the receipt with the fresh capability-snapshot digest immediately before
`spawn_agent`; bind the returned worker reference after the spawn succeeds;
finish or abandon the same receipt after the quality gate. If spawning fails,
close it as abandoned immediately. A pending receipt is not a completed run.

Run `scripts/evaluate-routing-receipts.py` to produce recommendations. A
task-class override requires at least 30 recent receipts, at least five samples
for each of Luna, Terra, and Sol, a 100% acceptance rate with no severe errors
for the winning candidate, and at least a 10% verified-completions-per-minute
lead over the next passing route. These are minimum gates, not an instruction
to run unsafe experiments. Canary only work with deterministic verification and
safe retry. A private profile may use stricter gates and is responsible for
atomic install, rollback, host verification, and expiration.

Natural usage is observational rather than a perfect randomized trial. Treat a
promotion as a reversible local optimization, expire it after 30 days, and
continue recording outcomes. Never generalize a task-class winner into a global
main model. Route promotion applies to workers; the owner controls the main model.

## Decision And Authority Envelope

Every worker gets one public-safe routing decision conforming to
`schemas/routing-decision.schema.json`. It contains the task class, model,
thinking level, routing mode, evidence state, execution level, rationale,
quality gate, escalation trigger, and authority envelope. A probe route also
declares `escalation_route`. Put the envelope in the worker's opening instruction:

A Terra decision also carries `calibration`: the receipt reference, Luna and
Sol comparison set, at least three runs per candidate, and the
`verified_completions_per_minute` metric. Without that evidence, Terra is not a
valid default route. A bounded `trial` is the explicit exception described above.

- `allowed`: the bounded actions the worker may take.
- `prohibited`: actions outside its scope or approval boundary.
- `proof_required`: evidence required before it reports completion.
- `stop_conditions`: conditions that require it to stop and report back.

Pass the exact decision `model` and `thinking` values to the requested worker
kind. For a durable thread, pass them to `create_thread`, then title and pin
only after native controls validate. Never title or pin a subagent. Do not
create a worker if the runtime cannot accept the requested values; use manual
mode and say what was unavailable.

Reroute mid-task only for a material quality, time, or failure-risk gain. Record
the replacement decision and why the gain is material.

Durable threads receive explicit model and thinking values. A native subagent
with `fork_turns: none` or a bounded positive value may receive an explicit
model and thinking override. A full-history fork inherits the parent's model
and thinking and cannot receive an override. Do not describe these mechanisms
as interchangeable or use `fork_turns: all` for a mixed-model packet.

## Main Agent and Unavailable Routes

Preserve the user's selected main model and effort. If the requested worker
route is unavailable, record requested and resolved model/effort plus the
verified limitation in `route_resolution`. An Astra-capable workflow may use
Sol when Astra is not live, entitled, or allowed. Use Luna for clear repeatable
work and Terra only with trial or promotion evidence. Never silently substitute
an unsupported effort, and never overwrite config to make a worker route fit.
If no eligible route can meet the gate, keep the work with the conductor or
report the exact unavailable capability.

## Concurrency and Nesting

Before every spawn, obtain a fresh inventory of all active workers under the
root task. Set `fanout.active_workers` to the other active workers and
`requested_workers` to the new batch size. The total must fit both the live
runtime capacity and the default cap of three. A larger team requires an
explicit owner request, recorded as `delegation_request_ref`, and remains
limited to ten independent, deterministic, noncolliding workers. Metadata
references record authority; they do not create it.

Workers cannot delegate by default. A depth-two packet or permission to nest
also requires `delegation_request_ref`; descendants share the root concurrency
budget. No depth greater than two or worker Ultra is allowed. A stricter
runtime or project instruction always wins. The standalone validator checks
the declared counts; only the conductor's fresh inventory establishes live
concurrency. Durable tasks still require an explicit user request.

## Advisory Exceptions

An approved non-OpenAI planner, reviewer, or council may provide narrow advice
when it has a documented advantage. It is not the executing worker, has no
operational authority, and must include a specific `advisory_fallback.reason`.

## Public Engine, Private Profile

This kit publishes the routing engine: generic task classes, model choices,
authority envelopes, schema, and sanitized examples. A local project may
maintain a private profile with its own work history, tools, policies, or
examples. Do not copy private profiles, names, account details, paths,
credentials, customer data, or private proof into this public kit.
