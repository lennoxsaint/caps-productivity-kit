# CAPS Stable Update

Resolve `project_root` from the native automation's registered project working
directory. Require both `.caps/install-manifest.json` and
`.caps/scripts/caps-update.py` below that root. If either is missing, make no
changes and report `caps_project_root_unavailable`.

Run the installed CAPS updater with explicit, quoted absolute paths:

```bash
project_root="$(pwd -P)"
test -f "$project_root/.caps/install-manifest.json"
test -f "$project_root/.caps/scripts/caps-update.py"
python3 "$project_root/.caps/scripts/caps-update.py" \
  --project "$project_root" check
```

If the result is `current`, report the installed version and stop. If it is a
compatible, non-disruptive `update_available`, run:

```bash
python3 "$project_root/.caps/scripts/caps-update.py" \
  --project "$project_root" apply
```

Report the installed version, updated file count, preserved local overrides,
backup directory, and release notes link. If the update is disruptive,
incompatible, cannot verify its artifact digest, or fails verification, do not
apply it. Preserve the current installation and report the exact blocker.

Never overwrite `.caps/config`, `.caps/state`, secrets, user data, or non-managed
files. Never weaken compatibility or digest checks. Rollback is available with:

```bash
python3 "$project_root/.caps/scripts/caps-update.py" \
  --project "$project_root" rollback
```
