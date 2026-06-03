# CAPS Productivity Kit

Set up a practical Codex Agent Productivity System in your own projects.

CAPS is a lightweight operating layer for using Codex as a project conductor with focused worker threads. It gives you repeatable instructions, naming conventions, handoff prompts, and installable templates so your agents stop acting like one-off chats and start acting like a coordinated system.

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
- Lane-tree diagrams for brain-dump routing
- Worker-thread prompts for implementation, research, QA, docs, and review lanes
- Naming and pinning conventions for keeping active work findable
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
  bootstrap/
  prompts/
  templates/
  docs/
  examples/
  packs/
```

Then, in Codex, run the installed bootstrap prompt:

```text
Read .caps/bootstrap/start-caps-conductor.md and execute it.
```

The bootstrap creates one project-scoped `CAPS CONDUCTOR` thread, titles it, and
pins it when Codex exposes `create_thread`, `set_thread_title`, and
`set_thread_pinned`. If those tools are missing, it reports the exact skipped
step and gives manual-mode instructions.

## How CAPS Works

CAPS has three layers:

1. `AGENTS.md` tells Codex how to behave in the workspace.
2. The `CAPS CONDUCTOR` thread owns planning, routing, evidence, and final
   decisions.
3. Worker threads handle bounded lanes such as implementation, QA, docs, research, or review.

Optional packs add a fourth layer: reusable setup material for a cohort, product, team, or launch shape. Packs can include lane templates, prompt schedules, skill manifests, and setup docs. They must stay public-safe: no secrets, no member data, no private thread IDs, and no proprietary launch proof unless that material has been explicitly cleared for publication.

The point is not to create bureaucracy. The point is to make the next action obvious, preserve proof, and avoid losing work in a pile of anonymous chat tabs.

When the conductor separates a brain dump into multiple lanes, it should show a
small lane tree first. Mermaid is the default because it stays text-native and
copyable. SCDiagram or a native image jam can be used when the split needs a
richer visual artifact. The tree is a review aid, not proof, and should keep
private details generic.

## Recommended Thread Pattern

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

Pin only active threads. Archive stale threads when the decision or deliverable is captured.

## Repo Layout

```text
.
├── AGENTS.md
├── README.md
├── install.sh
├── scripts/
│   └── verify.sh
├── templates/
│   ├── AGENTS.caps-lane-factory.md
│   ├── AGENTS.global.md
│   └── AGENTS.repo.md
├── prompts/
│   ├── bootstrap-caps-conductor.md
│   ├── conductor.md
│   ├── adjacent-repo-router.md
│   └── workers/
│       ├── docs.md
│       ├── implementation.md
│       ├── qa.md
│       ├── research.md
│       └── review.md
├── docs/
│   ├── setup-guide.md
│   ├── naming-and-pinning.md
│   ├── conductor-workflow.md
│   ├── operator-loop.md
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
Conductor may create, title, and pin pack-specific lanes later when the active
Codex runtime exposes safe thread-control tools.

## Verification

Run:

```bash
./scripts/verify.sh
```

This checks that required files exist, prompts are present, and the installer is executable.

## License

MIT. Use it, remix it, ship with it.
