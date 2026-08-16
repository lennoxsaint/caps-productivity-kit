# GPT-5.6 Routing

CAPS 0.4.0 routes worker work for verified successful work per minute, including
retries and rework through the acceptance gate. Keep quick answers,
clarifications, and tightly coupled work in the conductor. Create a worker only
for an independent deliverable or proof lane.

Evidence basis: OpenAI positions Sol for complex work, Terra for everyday
reasoning/tool use, and Luna for clear repeatable work. Artificial Analysis finds
Terra dominated on its aggregate intelligence-per-dollar index, but task-specific
coding results do not establish universal dominance. CAPS therefore requires
local comparative evidence before selecting Terra. See the
[OpenAI model guide](https://learn.chatgpt.com/docs/models?surface=app),
[OpenAI GPT-5.6 results](https://openai.com/index/gpt-5-6/), and
[Artificial Analysis methodology](https://artificialanalysis.ai/methodology).

Official API pricing verified on 2026-07-31 is $0.20 input / $1.20 output per
million tokens for Luna, $2 / $12 for Terra, and $5 / $30 for Sol. Price changes
expand the candidate set; they do not lower the acceptance, safety, or proof
gate. See the official [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), and
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol) model pages.

## Hybrid worker packet

Every routed worker declares `worker_kind: subagent | durable_thread`. Use a
native `subagent` for bounded same-task work; it is never titled or pinned. Use
`durable_thread` only for an explicit user request, future follow-up, separate
history, host or worktree, ongoing incident, or release coordination. Start
with at most four workers and scale to at most ten only for independent,
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
delegate by default; explicit nested delegation stops at depth two. Ultra is
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
| Rare, indivisible hardest problem | `gpt-5.6-sol` | `max` |
| Rare, high-value task with multiple genuinely independent workstreams | `gpt-5.6-sol` | `ultra` |

Terra is not a guaranteed middle lane. It is an evidence-gated exception: use
it only when repeated personal evals or runtime receipts show better verified
completions per minute than passing Luna and Sol candidates for that work shape.
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
3. Use Terra only when `personal_eval` or `runtime_observation` shows it beats
   both the passing Luna route and the relevant Sol route on verified successful
   work per minute.
4. Use Sol when ambiguity, integration judgment, polish, proof, or failure cost
   makes a probe wasteful.
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
manual default without broader cross-class evidence.

## Decision And Authority Envelope

Every worker gets one public-safe routing decision conforming to
`schemas/routing-decision.schema.json`. It contains the task class, model,
thinking level, routing mode, evidence state, execution level, rationale,
quality gate, escalation trigger, and authority envelope. A probe route also
declares `escalation_route`. Put the envelope in the worker's opening instruction:

A Terra decision also carries `calibration`: the receipt reference, Luna and
Sol comparison set, at least three runs per candidate, and the
`verified_completions_per_minute` metric. Without that evidence, Terra is not a
valid operational route.

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

## Manual Fallback

When a task must be done manually, start at `gpt-5.6-sol` with `medium`
thinking. Emit a one-line switch recommendation only when the route is a
material mismatch. Continue unless the mismatch is severe; a severe mismatch
means the current route cannot meet the required proof, safety, or quality gate.

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
