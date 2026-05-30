# Packs

Packs make CAPS reusable for a cohort, product, launch, or team without turning
the core kit into a pile of private operating notes.

## Contract

A pack lives at:

```text
packs/<pack-name>/
```

Required files:

```text
pack.yaml
README.md
setup.md
prompt-schedule.md
skill-manifest.md
lanes/
```

Recommended lane files:

```text
lanes/mission-control.md
lanes/build-lane.md
lanes/research-lane.md
lanes/qa-lane.md
lanes/review-lane.md
```

## Metadata

`pack.yaml` must include:

```yaml
id: example-pack
name: "Example Pack"
status: "template|placeholder|ready"
public_safe: true
summary: "What this pack helps a team do."
```

Use `status: "placeholder"` when the operating shape is known but source
materials have not been classified for public use yet.

## Public-Safe Rules

Packs must not contain:

- Secrets, tokens, or credentials.
- Private customer, member, student, or client data.
- Private thread IDs or internal dashboard URLs.
- Paid cohort lesson content unless it is explicitly cleared for publication.
- Local-only proof, launch gates, receipts, or business-sensitive details.

If a private team has not returned a public/private inventory, ship only the
generic pack contract and placeholders.

## Runtime Limits

Packs can provide:

- Prompts.
- Lane templates.
- Setup docs.
- Checklists.
- Skill or capability manifests.

Packs cannot guarantee automatic thread creation, pinning, renaming, or tab
installation. Those actions depend on the active Codex runtime and exposed
tools. If the runtime exposes safe thread-management tools, a conductor may use
them only within the current project instructions and user-approved boundaries.

## Install

Install a pack with:

```bash
./install.sh /path/to/project --pack pack-name
```

The pack is copied to:

```text
.caps/packs/pack-name/
```

Read the pack setup doc before using its prompts.
