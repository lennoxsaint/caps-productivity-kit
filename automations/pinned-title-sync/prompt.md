# CAPS Pinned Title Sync

Reconcile active pinned Codex thread titles with the task each thread is
currently working on. Titles are coordination metadata, never execution proof.

## Capability gate

Resolve `project_root` from the native automation's registered project working
directory. Require `.caps/config/title-preferences.json` and
`.caps/scripts/title-sync-policy.py` below that root. If either is missing,
make no changes and report `caps_project_root_unavailable`.

Require native read and mutation controls for Codex threads, including listing
or reading pinned threads and `set_thread_title`. If those controls are absent,
make no changes and report `native_thread_controls_unavailable`. Never mutate
Codex databases, session indexes, or global state files.

## Every run

1. Read `$project_root/.caps/config/title-preferences.json` and
   `$project_root/.caps/state/title-sync.json`. Respect global, project, and
   thread opt-outs.
   If a native title event or explicit owner instruction shows a manual title
   or emoji choice, record `manual_override` before evaluating automatic
   changes. Clear it only after an explicit owner request.
2. Inspect only active pinned threads. Use task-state events since the previous
   run when available; otherwise inspect the smallest current thread evidence
   needed to identify a material state change. Event signals accelerate the
   decision, while this twenty-minute run remains the reconciliation fallback.
3. Build one redacted snapshot per thread containing its current title,
   project, category, task-state revision, concise proposed action title,
   material-change flag, evidence references, and whether completion is
   verified. Do not put prompts, private content, secrets, or customer data in
   state or audit files.
4. Pipe the snapshot JSON over stdin to:

   ```bash
   project_root="$(pwd -P)"
   python3 "$project_root/.caps/scripts/title-sync-policy.py" evaluate \
     --config "$project_root/.caps/config/title-preferences.json" \
     --state "$project_root/.caps/state/title-sync.json"
   ```

5. Apply only decisions whose action is `rename`, using native
   `set_thread_title`. Preserve owner wording and explicit manual overrides.
   Never add `DONE`, `COMPLETE`, `SHIPPED`, `LIVE`, `MERGED`, `DEPLOYED`, or an
   equivalent completion claim without verified evidence.
6. Record every rename, no-op, manual override, and failure by piping a
   redacted result to:

   ```bash
   python3 "$project_root/.caps/scripts/title-sync-policy.py" record \
     --state "$project_root/.caps/state/title-sync.json" \
     --audit "$project_root/.caps/state/title-sync-audit.jsonl"
   ```

## Guardrails

- A user title or emoji choice persists until changed or cleared.
- Automatic emoji selection is project first, then task category.
- Existing pinned titles stay unchanged until a material,
  evidence-supported task-state change.
- Use concise action-oriented titles, capped at 48 characters.
- Do not rename more often than the policy permits.
- A failed rename leaves the current title intact. Record the error code and
  retry only on a later event or scheduled run.
- Do not create, unpin, archive, complete, message, deploy, or otherwise act on
  a thread as part of title synchronization.
