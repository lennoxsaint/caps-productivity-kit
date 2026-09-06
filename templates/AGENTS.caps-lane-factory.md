<!-- BEGIN CAPS MANAGED: lane-factory -->
## CAPS Lane Factory

This workspace uses CAPS, the Codex Agent Productivity System.

- Treat the active CAPS conductor as the normal entry point for messy work.
- The default worker kind is `subagent`: bounded same-task work stays native,
  untitled, and unpinned. It may read, analyze, test, or make a declared
  disjoint reversible local edit. Within the current request's authority,
  delegate it automatically without per-worker approval using `spawn_agent`,
  `list_agents`, `send_message`, `followup_task`, `wait_agent`, and
  `interrupt_agent`.
- Use `durable_thread` only for an explicit user request, future follow-up,
  separate history, host or worktree, ongoing incident, or release
  coordination. A durable thread is the only worker kind that may be titled
  or pinned.
- Route work to an existing durable lane before creating a duplicate durable
  lane. Keep quick answers and tightly coupled work in the conductor.
- Start with at most three concurrent workers. Expand only on an explicit owner request, up to ten when lanes are
  independent, deterministic, and non-colliding with separate write owners.
  Count all active descendants against the root cap before every spawn.
- Before every worker, create a routing decision using
  `.caps/docs/gpt-5-6-routing.md` and `.caps/schemas/routing-decision.schema.json`.
  Complete its redacted task snapshot before routing, then include the snapshot
  and authority envelope in the worker prompt.
- Optimize verified successful work per minute, including retries and rework.
  Astra handles demanding end-to-end work, Sol complex bounded work, and Luna
  clear repeatable work. Trial Terra only with deterministic checks and safe
  retry; default-route promotion requires real comparative evidence.
- Validate worker kind, model, thinking, `fork_turns`, and (for durable
  threads) native title/pin controls before execution. Never silently
  substitute a capability. For a mixed-model packet, `fork_turns` is `none`
  by default; a bounded positive value may also use an explicit model/thinking
  override. `fork_turns: all` inherits the parent model/thinking and cannot
  accept an override. No fork mode changes the packet's authority.
- Build the capability snapshot with `.caps/scripts/capability-snapshot.py`
  from a fresh live Codex runtime or App Server catalog with provenance and a
  capture time. Manual lists, examples, screenshots, and stale snapshots are
  not live capability truth.
- When a validated durable thread is created, pass the routing decision's
  exact resolved `model` and `thinking` values to `create_thread`, then title
  and pin it. Subagents never call title or pin controls.
- Reroute only for a material quality, time, or failure-risk gain. Manual work
  preserves the user-selected main model and reasoning effort; worker routing
  never overwrites either setting.
- Ultra is root-only. Workers cannot delegate by default. An explicit owner request recorded in the packet
  may allow nested delegation to depth two, but Ultra may not be assigned below
  the root. Do not confuse inherited subagents with durable threads.
- Non-OpenAI planner, reviewer, or council use is advisory-only and requires a
  written reason; it cannot replace the executing worker.
- Use short uppercase action-first titles, capped at 48 characters without
  cutting mid-word, only for durable threads.
- Treat titles and emoji as coordination metadata, not completion proof.
  Preserve owner overrides; automatic title sync requires a material,
  evidence-supported task-state change and native thread controls.
- When a brain dump is split across lanes, show a compact lane tree using
  Mermaid by default; use SCDiagram or native image jam only when useful, and
  keep sensitive details generic.
- If required capability or thread-control tools are unavailable, report the
  exact skipped step and do not silently downgrade or reclassify the worker.
- Do not mutate Codex state files directly.
- For each worker, start a redacted receipt with the capability-snapshot digest,
  bind the returned worker reference, then finish or abandon it. Close spawn
  failures as abandoned immediately.
- Every packet needs worker kind, outcome, workspace, one write owner and file
  set, stop condition, proof requirement, approval gates, delegation depth,
  receipt mode, and (for durable threads) an unpin rule.
- Prohibit external sends, production writes, merge, deploy, publish,
  credential changes, irreversible actions, and authority widening unless a
  separate current authority gate explicitly permits them.
<!-- END CAPS MANAGED: lane-factory -->
