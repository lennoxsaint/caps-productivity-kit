# Subscription-Value Routing

CAPS aims for more verified useful work from the existing subscription, counting
retries, review, and later corrections. This is a policy to evaluate, not a claim
that Luna Max or six workers are proven cheaper. Raw-token reductions do not
establish subscription allowance savings. Unknown consumption stays unknown.
The filename is retained for upgrade compatibility.

## Defaults and owner choices

Fresh installations default new interactive tasks to `gpt-6-astra` with `low`
reasoning. Preserve the selected model and effort in existing tasks. Explicit
owner overrides win; upgrades preserve existing explicit settings.

The default worker is `gpt-5.6-luna` with `max` reasoning. A specialist's role
instructions and permissions remain useful without stale model/effort pins.
Remove only identified stale pins in an approved configuration update; do not
erase owner-selected overrides. Keep standard service tier, context settings,
and memory settings unchanged. Do not enable Fast mode for speculative savings.

Use the documented runtime schema for worker defaults and concurrency. A
configuration parse is not effective-behavior proof: verify fresh generic and
specialist sessions after activation. Unsupported keys or routes must be
disclosed, not silently replaced.

## Bounded cascade

1. Define the outcome, source references, acceptance checks, ownership,
   authority, and stop conditions in a compact self-contained packet.
2. Start Luna Max. A lead may choose Sol Extra High first for difficult
   reasoning or consequential correctness, with a concrete recorded reason.
3. After failed acceptance, allow one targeted Luna correction if useful.
   Otherwise proceed directly to one Sol Extra High (`xhigh`) attempt.
4. If still unresolved, use one separate Astra Medium worker attempt.
5. Stop and report after exhaustion. Do not reset the budget by renaming the
   task, spawning a fresh worker at the same tier, or hiding earlier attempts.

`scripts/subscription-routing.py` plans this sequence from a per-task attempt
history and capability catalog. It never launches workers or changes policy.
An `accepted` history entry requires task-specific checks plus lead review.
The lead reviews returned evidence without repeating the whole investigation.

An unavailable model/effort combination advances to the next approved tier;
record every skipped route and its limitation. Missing credentials, permission,
source evidence, or infrastructure stop model escalation. Restore the missing
prerequisite within existing authority, or report the blocker. A more expensive
model is not a substitute for evidence or access. If all approved tiers are
unavailable, stop; do not loop back to a lower tier.

## Worker contract

Keep quick answers and tightly coupled work with the lead. Delegate only an
independent bounded outcome that materially helps. Use native `subagent` for
same-task work, untitled and unpinned. Create a `durable_thread` only when the
user explicitly asks for a separate or continuing task. Use real native controls
and report unavailable controls rather than mutating Codex state files.

Use `fork_turns: none` and compact packets by default. Bounded inheritance needs
a reason. `fork_turns: all` inherits the parent model and effort and cannot accept
overrides; it is not the mixed-model default. Preserve root model and effort.
Ultra is root-only and is never an escalation worker route.

Allow at most six workers per root, excluding the lead. Six is a ceiling, not a
target. Count all active descendants and durable workers belonging to the task
before every spawn; obey a smaller live runtime or project limit. The validator
checks declared counts, not the actual live inventory. No automatic nesting;
explicitly authorized nesting remains depth-limited to two and shares the cap.

Assign one writer per overlapping file set. Resolve symlink aliases to the same
workspace before checking ownership. `check_lanes` in the routing planner checks
exact root-relative files/directories against new and active writers; wildcard
or parent-traversal ownership is rejected. Read-only workers can share sources.

Every packet declares worker kind, exact outcome/workspace, evidence references,
acceptance checks, one write owner/file set, authority, stop conditions,
delegation depth, and receipt mode. Use `templates/worker-packet.md`.

Local reads, analysis, tests, and declared reversible edits are the worker
ceiling. External sends, production writes, merge, deploy, publish, credential
changes, irreversible actions, and authority widening retain separate current
approval gates. Routing metadata never creates authority.

## Capability-bound decisions

Export a fresh live Codex runtime/App Server catalog with provenance and capture
time; normalize it with `scripts/capability-snapshot.py`. Validate decisions with
`scripts/verify-routing.py` and `schemas/routing-decision.schema.json` before
spawn. Manual lists, examples, screenshots, and stale snapshots cannot authorize
a live route. Validate model, effort, worker kind, fork mode, and required native
controls. Record requested/resolved routes and `route_resolution` for unavailable
tiers. Quality escalation is a new decision with a new requested route and linked
attempt evidence, not a false claim that the prior model became unavailable.

The generic decision schema retains legacy model examples for compatibility and
explicit owner exceptions. They are not the default subscription cascade. Terra
trials or other routes require a separate explicit owner decision; external
benchmarks do not promote them into saved defaults. Non-OpenAI advice needs a
specific reason and has no operational authority.

## Evidence and learning

Extend the existing private receipt store; do not create a parallel tracker.
Start before spawn, bind the actual worker reference, and finish or abandon.
Close failed spawns as abandoned. Capture model/effort, task class, checks,
outcome, attempts, escalation reason, elapsed time, available usage, and later
owner corrections. Missing usage is unknown, never zero. A worker's answer alone
does not pass acceptance. Later corrections count as rework.

Keep metadata redacted: no raw transcripts, answers, secrets, customer content,
or private usage evidence in public artifacts. Use normal task receipts, not
routine duplicate benchmarks. Comparisons must acknowledge differing task
difficulty, incomplete evidence, and review cost. Synthetic fixtures verify
software behavior; they do not prove a subscription-value winner.

`scripts/evaluate-routing-receipts.py` provides recommendations only. No evaluator,
reconciler, or scheduled digest automatically promotes saved routing policy.
Policy changes need an explicit owner decision and verified rollout. A weekly
private digest may include a short routing lesson only when new evidence exists;
no separate model polling or benchmark quota is required.

## Rollout and proof

Prepare exact target-specific diffs before configuration activation. After
approval: back up, verify drift, apply atomically, and verify hosts sequentially.
Stop on a failed host and preserve earlier verified results. Rollback restores
only this update and refuses to overwrite subsequent owner edits.

Distinguish local tests, installed configuration, effective fresh-session
behavior, scheduled execution, and public release. Functional verification can
prepare a release immediately; no mandatory observation week. Publication remains
a separate approval gate. Private digests do not block release of the public kit.
