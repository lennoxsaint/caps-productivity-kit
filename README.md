# CAPS Productivity Kit

Set up a practical Codex Agent Productivity System in your own projects.

CAPS is a lightweight operating layer for using Codex as a project conductor with focused worker threads. It gives you repeatable instructions, naming conventions, handoff prompts, and installable templates so your agents stop acting like one-off chats and start acting like a coordinated system.

This kit is intentionally plain. No SaaS. No dashboard. No magic. Clone it, run the installer, and adapt the templates to your workspace.

## What You Get

- Global and repo-local `AGENTS.md` templates
- A conductor prompt for the main coordinating thread
- Worker-thread prompts for implementation, research, QA, docs, and review lanes
- Naming and pinning conventions for keeping active work findable
- A read-first operator loop for "what did I miss?" triage
- A proof-state matrix for drafts, queues, sends, publishing, deploys, and live verification
- A setup guide for new workspaces
- Optional cohort/product/team packs
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
  prompts/
  templates/
  docs/
  examples/
  packs/
```

Then open your project in Codex and start a conductor thread with:

```text
Use .caps/prompts/conductor.md as the operating prompt for this workspace.
Read AGENTS.md first, then help me plan and execute the next project slice.
```

## How CAPS Works

CAPS has three layers:

1. `AGENTS.md` tells Codex how to behave in the workspace.
2. The conductor thread owns planning, routing, evidence, and final decisions.
3. Worker threads handle bounded lanes such as implementation, QA, docs, research, or review.

Optional packs add a fourth layer: reusable setup material for a cohort, product, team, or launch shape. Packs can include lane templates, prompt schedules, skill manifests, and setup docs. They must stay public-safe: no secrets, no member data, no private thread IDs, and no proprietary launch proof unless that material has been explicitly cleared for publication.

The point is not to create bureaucracy. The point is to make the next action obvious, preserve proof, and avoid losing work in a pile of anonymous chat tabs.

## Recommended Thread Pattern

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
│   ├── AGENTS.global.md
│   └── AGENTS.repo.md
├── prompts/
│   ├── conductor.md
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

After installing, edit your project `AGENTS.md`:

- Add the real project goal.
- Add commands for install, test, lint, build, and deploy.
- Add safety rules for production, payments, secrets, and customer data.
- Add repo-specific architecture notes.
- Add the definition of done for your product.

Keep global rules stable. Keep project rules local. Keep reusable prompts in `.caps/prompts`.

## Packs

Packs live under `packs/<pack-name>/`. A pack can define:

- `pack.yaml` for metadata and safety status
- `setup.md` for install and customization steps
- `prompt-schedule.md` for when to use conductor and worker prompts
- `skill-manifest.md` for optional skills or capabilities
- `lanes/` for reusable conductor and worker lane templates

Packs do not automatically create, pin, or rename Codex threads. The kit can provide prompts, checklists, and scripts, but app-level pinning or thread automation depends on what the active Codex runtime exposes.

## Verification

Run:

```bash
./scripts/verify.sh
```

This checks that required files exist, prompts are present, and the installer is executable.

## License

MIT. Use it, remix it, ship with it.
