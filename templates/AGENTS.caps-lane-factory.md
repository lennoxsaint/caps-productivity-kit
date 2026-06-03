<!-- BEGIN CAPS MANAGED: lane-factory -->
## CAPS Lane Factory

This workspace uses CAPS, the Codex Agent Productivity System.

- Treat the active CAPS conductor as the normal entry point for messy work.
- Pinned Codex threads are today's active work lanes; unpinned threads are
  reference, backlog, or done.
- Route work to an existing pinned lane before creating a duplicate lane.
- Create a new worker lane only when the outcome is clear, active, and not
  already owned.
- When thread-control tools are available, create new lanes with `create_thread`,
  then immediately call `set_thread_title` and `set_thread_pinned`.
- Use short uppercase action-first titles, capped at 48 characters without
  cutting mid-word.
- When a brain dump is split across lanes, show a compact lane tree using
  Mermaid by default; use SCDiagram or native image jam only when useful, and
  keep sensitive details generic.
- If thread-control tools are unavailable, report the exact skipped step and
  give manual-mode copy/paste instructions.
- Do not mutate Codex state files directly.
- Every worker lane needs an outcome, workspace, stop condition, proof
  requirement, approval gates, and unpin rule.
<!-- END CAPS MANAGED: lane-factory -->
