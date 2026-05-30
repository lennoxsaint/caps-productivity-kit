# CAPS Productivity Kit

Set up a practical Codex Agent Productivity System in your own projects.

CAPS is a lightweight operating layer for using Codex as a project conductor with focused worker threads. It gives you repeatable instructions, naming conventions, handoff prompts, and installable templates so your agents stop acting like one-off chats and start acting like a coordinated system.

This kit is intentionally plain. No SaaS. No dashboard. No magic. Clone it, run the installer, and adapt the templates to your workspace.

## What You Get

- Global and repo-local `AGENTS.md` templates
- A conductor prompt for the main coordinating thread
- Worker-thread prompts for implementation, research, QA, docs, and review lanes
- Naming and pinning conventions for keeping active work findable
- A setup guide for new workspaces
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

The installer creates:

```text
AGENTS.md
.caps/
  prompts/
  templates/
  docs/
  examples/
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
│   └── evidence-and-handoffs.md
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

## Verification

Run:

```bash
./scripts/verify.sh
```

This checks that required files exist, prompts are present, and the installer is executable.

## License

MIT. Use it, remix it, ship with it.
