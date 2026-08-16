# CAPS Worker Packet

Copy this public-safe packet into a worker prompt and replace the placeholders.
Do not include raw conversation history, secrets, customer data, private paths,
or private thread IDs.

```yaml
worker_packet:
  worker_kind: "subagent" # subagent | durable_thread
  objective: "[ONE_BOUNDED_OUTCOME]"
  task_snapshot:
    scope: "[EXACT_SCOPE]"
    acceptance_gate: "[HOW_TO_PROVE_IT]"
    risk: "[LOW|MEDIUM|HIGH]"
    side_effects: "[LOCAL_ONLY_OR_EXACT_SURFACES]"
    evidence_refs: ["[PUBLIC_OR_LOCAL_REF]"]
    stop_conditions: ["[STOP_AND_REPORT_CONDITION]"]
  route:
    model: "gpt-5.6-sol"
    thinking: "medium"
    fork_turns: "none" # none or bounded may override; all must inherit parent route
    capability_snapshot_digest: "sha256:[LIVE_RUNTIME_SNAPSHOT_DIGEST]"
  ownership:
    write_owner: "[WORKER_NAME_OR_CONDUCTOR]"
    file_set: ["[EXACT_FILE_OR_DIRECTORY]"]
    mode: "local-edit" # inspect-only | test-only | local-edit | draft-only
  capabilities:
    required: ["[MODEL]", "[THINKING]", "[WORKER_KIND]"]
    title_and_pin_required: false
    validated: false
  authority:
    allowed:
      - "read local sources"
      - "analyze and run bounded tests"
      - "make only declared reversible local edits"
    prohibited:
      - "external sends or posts"
      - "production writes, payments, or account changes"
      - "merge, deploy, publish, or release execution"
      - "credential, secret, permission, or authentication changes"
      - "destructive or irreversible actions"
      - "authority or file-set widening"
  delegation:
    may_delegate: false
    nested_depth: 0
    max_depth: 2
  receipt:
    mode: "redacted"
    lifecycle: "start -> bind spawned worker -> finish | abandon"
    degraded_observability_rule: "Report the gap; do not upgrade proof."
  output:
    status: "done | blocked | needs review"
    changed: ["[FILES_OR_NONE]"]
    verified: ["[COMMANDS_AND_RESULTS]"]
    proof_state: "[read|draft|queued|blocked|other]"
    next_gate: "[ONE_NEXT_ACTION_OR_NONE]"
```

Execution rules:

1. Validate capabilities before reading or editing. Never silently substitute a
   model, thinking level, worker kind, or proof state.
2. `subagent` is the default for same-task bounded work and is never titled or
   pinned. The conductor may create it automatically within current local,
   reversible authority using `spawn_agent`, `list_agents`, `send_message`,
   `followup_task`, `wait_agent`, and `interrupt_agent`. Use `durable_thread`
   only after an explicit user request and native control validation.
3. `fork_turns: none` is the mixed-model default. A bounded positive value may
   inherit needed context and still use an explicit model/thinking override.
   `fork_turns: all` inherits the parent model/thinking and cannot accept one.
4. Only `write_owner` edits `file_set`. Workers cannot delegate unless the
   packet opts in; nested delegation stops at depth two.
5. Build the snapshot digest from a fresh live-runtime catalog using
   `scripts/capability-snapshot.py`; manual lists, examples, screenshots, and
   stale snapshots are not availability truth.
6. Start the receipt before spawning, bind the returned worker reference, then
   finish or abandon it. Close a spawn failure as abandoned immediately.
7. Stop at every prohibited action and return the exact blocker and next gate.
