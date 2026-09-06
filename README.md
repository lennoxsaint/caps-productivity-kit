# CAPS Productivity Kit

Set up a practical Codex Agent Productivity System in your own projects.

CAPS is a lightweight operating layer for using Codex as a project conductor
with focused workers. It gives you repeatable instructions, authority packets,
naming conventions, handoff prompts, and installable templates so your agents
stop acting like one-off chats and start acting like a coordinated system.

This kit is intentionally plain. No SaaS. No dashboard. No magic. Clone it, run the installer, and adapt the templates to your workspace.

## What This Repo Is

`caps-productivity-kit` is the generic CAPS shell:

- Install patterns for a Codex Agent Productivity System.
- Conductor and worker prompts.
- Naming, pinning, proof, and handoff conventions.
- Generic pack contracts and sanitized examples.
- Optional links to adjacent product or workflow repos.

It is not:

- Paid Full Circle 5.0 access.
- The Full Circle course or student operating system.
- The Threadify app runtime.
- The owner of Threadify workflow recipes.
- A promise that shell install alone can create, pin, or rename app threads.
  That part happens through the installed Codex bootstrap when the active
  runtime exposes safe thread-control tools.

## What You Get

- Global and repo-local `AGENTS.md` templates
- A lane-factory `AGENTS.md` managed block
- A Codex bootstrap prompt for creating and pinning `CAPS CONDUCTOR`
- A conductor prompt for the main coordinating thread
- A hybrid worker contract: native `subagent` by default, exceptional
  `durable_thread` when persistence is justified
- One-write-owner packets, capability validation, delegation limits, and
  degraded-observability receipt rules
- Astra, Sol, Terra, and Luna worker routing with explicit model, thinking, and authority envelopes
- Redacted runtime routing receipts with conservative evidence evaluation
- Lane-tree diagrams for brain-dump routing
- Dynamic harness templates for complex, proof-sensitive work
- Worker prompts for implementation, research, QA, docs, and review lanes
- Naming and pinning conventions for keeping active work findable
- Optional project/category emoji and evidence-gated pinned-title sync
- Versioned stable updates with integrity checks, local-override preservation,
  and rollback
- A read-first operator loop for "what did I miss?" triage
- A proof-state matrix for drafts, queues, sends, publishing, deploys, and live verification
- A setup guide for new workspaces
- Optional cohort/product/team packs
- Adjacent-repo link templates for product-specific material
- Example workflows you can copy
- A small installer that copies the kit into an existing repo

## Quick Start

Clone this repo:

```bash
git clone https://github.com/lennoxsaint/caps-productivity-kit.git
cd caps-productivity-kit
```

Install CAPS into a project:

```bash
./install.sh /path/to/your/project
```

Install CAPS with a specific public-safe pack:

```bash
./install.sh /path/to/your/project --pack full-circle-5
```

The installer creates:

```text
AGENTS.md
.caps/
  automations/
  bootstrap/
  config/
  prompts/
  templates/
  docs/
  examples/
  packs/
  state/
```

Then, in Codex, run the installed bootstrap prompt:

```text
Read .caps/bootstrap/start-caps-conductor.md and execute it.
```

The bootstrap creates one project-scoped `CAPS CONDUCTOR` thread, titles it, and
pins it when Codex exposes `create_thread`, `set_thread_title`, and
`set_thread_pinned`. If those tools are missing, it reports the exact skipped
step and gives manual-mode instructions.

CAPS also installs paused automation proposals for Luna-powered pinned-title
reconciliation and stable updates. Generate a project-specific activation
prompt with:

```bash
python3 .caps/scripts/automation-doctor.py --project . activation
```

Give that output to Codex so its native Scheduled controls can upsert and read
back the jobs. The doctor distinguishes a copied proposal from a genuinely
active task and never writes Codex registry files. See
`docs/naming-and-pinning.md` and `docs/updates.md`.

## How CAPS Works

CAPS has three layers:

1. `AGENTS.md` tells Codex how to behave in the workspace.
2. The `CAPS CONDUCTOR` thread owns planning, routing, evidence, and final
   decisions.
3. Workers handle bounded lanes such as implementation, QA, docs, research, or
   review. Same-task work uses native subagents and is never titled or pinned.
   Durable threads are reserved for an explicit user request, future follow-up,
   separate history, host or worktree, ongoing incident, or release
   coordination.

Optional packs add a fourth layer: reusable setup material for a cohort, product, team, or launch shape. Packs can include lane templates, prompt schedules, skill manifests, and setup docs. They must stay public-safe: no secrets, no member data, no private thread IDs, and no proprietary launch proof unless that material has been explicitly cleared for publication.

The point is not to create bureaucracy. The point is to make the next action obvious, preserve proof, and avoid losing work in a pile of anonymous chat tabs.

When the conductor separates a brain dump into multiple lanes, it should show a
small lane tree first. Mermaid is the default because it stays text-native and
copyable. SCDiagram or a native image jam can be used when the split needs a
richer visual artifact. The tree is a review aid, not proof, and should keep
private details generic.

## Hybrid Worker Pattern

The default worker kind is `subagent`. Use it for bounded reads, analysis,
tests, or disjoint reversible local edits. A subagent receives a self-contained
packet and stays inside its one write owner's file set.

Use `durable_thread` only when persistence or separate coordination is actually
needed: an explicit user request, future follow-up, separate history, host or
worktree, ongoing incident, or release. Validate native thread controls before
creating one; only then title and pin it. A title or pin is coordination
metadata, never proof of completion.

Start with at most three concurrent workers. Expand only on an explicit owner request, up to ten for
independent, deterministic, non-colliding lanes. Workers cannot delegate by
default; an explicit packet may permit nested delegation to depth two. Ultra is
root-only. For mixed-model packets, `fork_turns: none` is the default and full
history cannot silently override the requested model or authority.

Read [`docs/hybrid-workers.md`](docs/hybrid-workers.md) and copy
[`templates/worker-packet.md`](templates/worker-packet.md) before routing.

## Recommended Durable Thread Pattern

The first pinned thread is:

```text
CAPS CONDUCTOR
```

Use short, uppercase, action-first thread names:

```text
BUILD AUTH FIX
QA CHECKOUT FLOW
REVIEW PR 42
DOCS INSTALL GUIDE
SHIP RELEASE 2026-05-30
```

Pin only active durable threads. Subagents cannot be pinned. Archive stale
durable threads when the decision or deliverable is captured.

## Repo Layout

```text
.
├── AGENTS.md
├── README.md
├── install.sh
├── scripts/
│   ├── verify-routing.py
│   ├── title-sync-policy.py
│   ├── automation-doctor.py
│   ├── caps-update.py
│   └── verify.sh
├── schemas/
│   └── routing-decision.schema.json
├── CONTEXT.md
├── templates/
│   ├── AGENTS.caps-lane-factory.md
│   ├── AGENTS.global.md
│   ├── AGENTS.repo.md
│   ├── authority-envelope.md
│   └── worker-packet.md
├── prompts/
│   ├── bootstrap-caps-conductor.md
│   ├── conductor.md
│   ├── adjacent-repo-router.md
│   └── workers/
│       ├── hybrid.md
│       ├── docs.md
│       ├── implementation.md
│       ├── qa.md
│       ├── research.md
│       └── review.md
├── docs/
│   ├── setup-guide.md
│   ├── hybrid-workers.md
│   ├── naming-and-pinning.md
│   ├── updates.md
│   ├── conductor-workflow.md
│   ├── gpt-5-6-routing.md
│   ├── operator-loop.md
│   ├── dynamic-harnesses.md
│   ├── evidence-and-handoffs.md
│   ├── adjacent-repos.md
│   └── packs.md
├── packs/
│   ├── README.md
│   ├── _template/
│   └── full-circle-5/
└── examples/
    ├── feature-build/
    └── release-check/
```

## What To Customize

After installing, review your project `AGENTS.md`:

- Add the real project goal.
- Add commands for install, test, lint, build, and deploy.
- Add safety rules for production, payments, secrets, and customer data.
- Add repo-specific architecture notes.
- Add the definition of done for your product.

The installer appends or updates one managed CAPS lane-factory block. It creates
a timestamped `AGENTS.md.backup-*` before modifying an existing file. Use
`--no-agents-update` if you want to install `.caps/` without touching
`AGENTS.md`.

Keep global rules stable. Keep project rules local. Keep reusable prompts in `.caps/prompts`.

## Adjacent Repos

CAPS can point to adjacent repos without absorbing their private or product-specific work.

- Full Circle should own FC5 student OS material, tier packs, gated links, and course-specific lesson bodies.
- Threadify-Workflows should own reusable creator-growth workflow recipes and templates.
- This repo owns only the generic CAPS shell, install patterns, routing prompts, proof contracts, and sanitized examples.

Use `docs/adjacent-repos.md` and `templates/adjacent-repo-link.md` when adding an approved link.

## Packs

Packs live under `packs/<pack-name>/`. A pack can define:

- `pack.yaml` for metadata and safety status
- `setup.md` for install and customization steps
- `prompt-schedule.md` for when to use conductor and worker prompts
- `skill-manifest.md` for optional skills or capabilities
- `lanes/` for reusable conductor and worker lane templates

Packs do not create, pin, or rename Codex threads from shell install. The
Conductor may create, title, and pin pack-specific durable lanes later when the
active Codex runtime exposes safe thread-control tools and the packet has a
qualifying persistence reason. Pack work that stays in the same task uses an
untitled, unpinned subagent.

## Verification

Run:

```bash
./scripts/verify.sh
```

This checks that required files exist, prompts are present, and the installer is executable.
It also validates public routing schema examples and the deterministic routing
matrix without third-party dependencies.

## License

MIT. Use it, remix it, ship with it.

## 0.5 routing upgrade

Astra handles demanding end-to-end work while Sol, Terra, and Luna remain
available for suitable bounded tasks. Main-model selection stays owner-controlled.
Automatic delegation defaults to three concurrent workers across the root task.
Larger teams and nesting require an explicit owner request. Terra may collect
evidence through safe bounded trials before default-route promotion.

Upgrading retains the existing routing-doc path and receipt schema. Old receipts
remain readable; their original eligibility checks still apply. The decision
schema adds optional trial and delegation-request fields and requires explicit
active-worker counts for new decisions. New spawns follow the new cap; legacy receipts are never rewritten.

Experimental context management is a separate opt-in, never enabled by the
public installer. Check client/account support and workspace requirements, then
back up config and verify a new task before claiming activation. See the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
