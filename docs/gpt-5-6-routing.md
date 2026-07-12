# GPT-5.6 Routing

CAPS routes real worker lanes for verified successful work per minute, including
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

Treat a synthetic fixture winner as provisional evidence, not permanent truth.
Recalibrate after 30 real task receipts or 30 days, whichever comes first.

## Decision And Authority Envelope

Every worker gets one public-safe routing decision conforming to
`schemas/routing-decision.schema.json`. It contains the task class, model,
thinking level, routing mode, evidence state, execution level, rationale,
quality gate, escalation trigger, and authority envelope. A probe route also
declares `escalation_route`. Put the envelope in the worker's opening instruction:

- `allowed`: the bounded actions the worker may take.
- `prohibited`: actions outside its scope or approval boundary.
- `proof_required`: evidence required before it reports completion.
- `stop_conditions`: conditions that require it to stop and report back.

Pass the exact decision `model` and `thinking` values to `create_thread`, then
title and pin the returned worker. Do not create a worker if the runtime cannot
accept those values; use manual mode and say what was unavailable.

Reroute mid-task only for a material quality, time, or failure-risk gain. Record
the replacement decision and why the gain is material.

`create_thread` workers receive explicit model and thinking values. Inherited
subagents may retain their parent's route. Do not describe these mechanisms as
interchangeable or use inherited subagents for a mixed-model plan.

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
