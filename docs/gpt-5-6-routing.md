# GPT-5.6 Routing

CAPS routes real worker lanes for quality per minute. Keep quick answers,
clarifications, and tightly coupled work in the conductor. Create a worker only
for an independent deliverable or proof lane.

## Worker Matrix

| Work shape | Model | Thinking |
| --- | --- | --- |
| Extraction, classification, transformation, indexing, repeatable structured summaries | `gpt-5.6-luna` | `low` |
| Bounded coding, routine tools, frozen-plan implementation, normal operator work | `gpt-5.6-terra` | `medium` |
| Multi-step work needing more planning or judgment | `gpt-5.6-terra` / `gpt-5.6-sol` | `high` / `medium` |
| Ambiguous architecture, deep research, incidents, consequential strategy, computer use, polished high-value deliverables | `gpt-5.6-sol` | `high` or `xhigh` |
| Rare, indivisible hardest problem | `gpt-5.6-sol` | `max` |
| Rare, high-value task with multiple genuinely independent workstreams | `gpt-5.6-sol` | `ultra` |

Max and Ultra are reasoning levels, not model IDs. Use Max only when the problem
cannot be safely split. Use Ultra only when the workstreams are genuinely
independent and their coordination has high value. Neither is a default for
urgency or a vague request.

## Decision And Authority Envelope

Every worker gets one public-safe routing decision conforming to
`schemas/routing-decision.schema.json`. It contains the task class, model,
thinking level, rationale, quality gate, escalation trigger, and authority
envelope. Put the envelope in the worker's opening instruction:

- `allowed`: the bounded actions the worker may take.
- `prohibited`: actions outside its scope or approval boundary.
- `proof_required`: evidence required before it reports completion.
- `stop_conditions`: conditions that require it to stop and report back.

Pass the exact decision `model` and `thinking` values to `create_thread`, then
title and pin the returned worker. Do not create a worker if the runtime cannot
accept those values; use manual mode and say what was unavailable.

Reroute mid-task only for a material quality, time, or failure-risk gain. Record
the replacement decision and why the gain is material.

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
