# CAPS Stable Update

Run the installed CAPS updater for this project:

```bash
python3 .caps/scripts/caps-update.py --project . check
```

If the result is `current`, report the installed version and stop. If it is a
compatible, non-disruptive `update_available`, run:

```bash
python3 .caps/scripts/caps-update.py --project . apply
```

Report the installed version, updated file count, preserved local overrides,
backup directory, and release notes link. If the update is disruptive,
incompatible, cannot verify its artifact digest, or fails verification, do not
apply it. Preserve the current installation and report the exact blocker.

Never overwrite `.caps/config`, `.caps/state`, secrets, user data, or non-managed
files. Never weaken compatibility or digest checks. Rollback is available with:

```bash
python3 .caps/scripts/caps-update.py --project . rollback
```
