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

The paused `caps-stable-update` Codex automation template checks daily and may
apply only verified, compatible, non-disruptive releases. Installing CAPS copies
the template but does not silently register or activate a global Codex
automation. Activation requires a Codex runtime with native automation support.
