# CAPS Updates

CAPS is distributed as a public Git repository and copied into a project by
`install.sh`. It is not a package-manager install or a hosted service.

## Update channel

Installed projects track the explicit `stable` channel. A channel manifest
declares:

- release version and artifact URL;
- SHA-256 artifact digest;
- supported install-schema range;
- minimum updater version;
- disruptive or non-disruptive status;
- release notes and rollback version.

Release artifacts are deterministic archives built by
`scripts/build-release.py`. A release is not usable by the updater until its
versioned artifact exists on GitHub and the channel manifest contains the exact
digest.

## Installed state

`install.sh` records `.caps/install-manifest.json` with the installed version
and hashes of managed files. It keeps user-owned state separate:

- `.caps/config/` contains local preferences;
- `.caps/state/` contains local runtime state and audit records;
- non-managed files and non-managed `AGENTS.md` content remain user-owned.

Verify either checkout layout with the verifier shipped in that layout:

```bash
# From the CAPS source repository
./scripts/verify.sh

# From a project with CAPS installed
.caps/scripts/verify.sh
```

The source-repository check keeps the complete release, pack, private-material,
artifact, routing, and test gates. The installed check auto-detects
`.caps/install-manifest.json` and checks only the mapped installed layout. It
verifies required installed files, managed-file SHA-256 hashes, declared local
overrides, routing schemas and examples, and the curated installed test suite.
It does not require source-only files such as `README.md`, `AGENTS.md`,
`install.sh`, release channels, or source packs.

## Check, apply, and rollback

```bash
python3 .caps/scripts/caps-update.py --project . check
python3 .caps/scripts/caps-update.py --project . apply
python3 .caps/scripts/caps-update.py --project . rollback
```

A safe apply verifies compatibility and artifact integrity, backs up files it
will replace, preserves locally modified managed files, and records clear status
in `.caps/state/update-status.json`. A disruptive release requires explicit
`--allow-disruptive`. A digest mismatch, incompatible schema, unavailable
artifact, or interrupted apply leaves the installed release in place.

The paused `caps-stable-update` Codex automation proposal checks daily and may
apply only verified, compatible, non-disruptive releases. Installing CAPS copies
the proposal but does not silently register or activate a global Codex
automation.

Generate the project-specific native activation request:

```bash
python3 .caps/scripts/automation-doctor.py --project . activation
```

The request uses the installed project's absolute prompt path and working
directory, asks native Scheduled controls to upsert by stable ID, and requires a
readback. Verify the registered task with:

```bash
python3 .caps/scripts/automation-doctor.py --project . inspect
```

Activation requires a Codex runtime with native Scheduled task support. The
doctor is read-only with respect to Codex's registry; missing controls remain an
explicit `native_automation_controls_unavailable` blocker.
