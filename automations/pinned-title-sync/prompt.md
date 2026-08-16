# CAPS Pinned Title Sync

Reconcile active pinned Codex thread titles with the task each thread is
currently working on. Titles are coordination metadata, never execution proof.

## Capability gate

Resolve `project_root` from the native automation's registered project working
directory. Require `.caps/config/title-preferences.json` and
`.caps/scripts/title-sync-policy.py` and
`.caps/scripts/pinned-thread-snapshot.py` below that root. If any is missing,
make no changes and report `caps_project_root_unavailable`.

Require native read and mutation controls for Codex threads, including Codex
app-server access and `set_thread_title`. The snapshot helper first discovers
the single case-insensitive `Pinned` section through `threadSection/list`,
then reads it through `thread/list` with `sectionId`. On older runtimes it may
fall back only when `threadSection/list` returns legacy JSON-RPC `-32600` or
method-not-found `-32601`, using the
legacy `isPinned=true` and `useStateDbOnly=true` filter. Missing, ambiguous,
empty-unverified, or mismatched section membership is fail-closed. These are read-only native
queries, not direct database access. If either native control is absent, make
no changes and report `native_thread_controls_unavailable`. Never mutate Codex
databases, session indexes, or global state files.

## Every run

1. Read `$project_root/.caps/config/title-preferences.json` and
   `$project_root/.caps/state/title-sync.json`. Respect global, project, and
   thread opt-outs.
   If a native title event or explicit owner instruction shows a manual title
   or emoji choice, record `manual_override` before evaluating automatic
   changes. Clear it only after an explicit owner request.
2. Get the authoritative active pinned-thread set with this bounded command:

   ```bash
   python3 "$project_root/.caps/scripts/pinned-thread-snapshot.py" \
     --page-size 50 --timeout-seconds 10
   ```

   Do not substitute `codex_app__list_threads(limit=100)`: that cross-host
   aggregation is not the authoritative pin-state source for this automation.
   If the helper fails, record its redacted error and report
   `native_thread_controls_unavailable` without renaming anything. Treat
   `pinned_filter_unsupported`, `pinned_filter_not_applied`, or
   `pinned_section_empty_unverified` as a Codex app-server compatibility
   failure; never continue by scanning unfiltered thread history or inferring
   pin state. Some upgraded runtimes retain legacy pin metadata outside the
   new section model, so an empty section is not accepted as proof.
3. Inspect only threads returned by that pinned snapshot. Use task-state events
   since the previous run when available; otherwise compare `updated_at` with
   the stored task-state revision and read only the smallest current thread
   evidence needed to identify a material state change. Event signals
   accelerate the decision, while this twenty-minute run remains the
   reconciliation fallback.
4. Build one redacted snapshot per thread containing its current title,
   project, category, task-state revision, concise proposed action title,
   material-change flag, evidence references, and whether completion is
   verified. Do not put prompts, private content, secrets, or customer data in
   state or audit files.
5. Pipe the snapshot JSON over stdin to:

   ```bash
   project_root="$(pwd -P)"
   python3 "$project_root/.caps/scripts/title-sync-policy.py" evaluate \
     --config "$project_root/.caps/config/title-preferences.json" \
     --state "$project_root/.caps/state/title-sync.json"
   ```

6. Apply only decisions whose action is `rename`, using native
   `set_thread_title`. Preserve owner wording and explicit manual overrides.
   Never add `DONE`, `COMPLETE`, `SHIPPED`, `LIVE`, `MERGED`, `DEPLOYED`, or an
   equivalent completion claim without verified evidence.
7. Record every rename, no-op, manual override, and failure by piping a
   redacted result to the command below. Include `state_revision` for every
   successful no-op so unchanged threads are not re-read on the next sweep.

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
- Never infer pin state from recency, runtime status, title text, project, or a
  `thread/list` row whose section membership does not match the discovered
  `Pinned` section.
- Use concise action-oriented titles, capped at 48 characters.
- Do not rename more often than the policy permits.
- A failed rename leaves the current title intact. Record the error code and
  retry only on a later event or scheduled run.
- Do not create, unpin, archive, complete, message, deploy, or otherwise act on
  a thread as part of title synchronization.
