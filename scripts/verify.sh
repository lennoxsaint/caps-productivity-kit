#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

verify_installed_layout() {
  [[ -f "$root/install-manifest.json" ]] || { echo "Missing installed file: install-manifest.json" >&2; return 1; }
  [[ -f "$root/config/installed-files.json" ]] || { echo "Missing installed file: config/installed-files.json" >&2; return 1; }

  bash -n "$root/scripts/verify.sh"
  python3 - "$root" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1]).resolve()
manifest_path = root / "install-manifest.json"
contract_path = root / "config/installed-files.json"
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"Invalid install manifest: {error}")
try:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"Invalid installed-file contract: {error}")

if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
    raise SystemExit("Invalid install manifest schema")
managed = manifest.get("managed_files")
overrides = manifest.get("local_overrides")
if not isinstance(managed, dict):
    raise SystemExit("Invalid install manifest managed_files")
if not isinstance(overrides, list) or any(not isinstance(item, str) for item in overrides):
    raise SystemExit("Invalid install manifest local_overrides")
if len(overrides) != len(set(overrides)):
    raise SystemExit("Duplicate local override declaration")

if not isinstance(contract, dict) or contract.get("schema_version") != "1.0":
    raise SystemExit("Invalid installed-file contract schema")
contract_files = contract.get("managed_files")
if not isinstance(contract_files, list) or any(not isinstance(item, str) for item in contract_files):
    raise SystemExit("Invalid installed-file contract managed_files")
required_managed = set(contract_files)
if len(required_managed) != len(contract_files):
    raise SystemExit("Duplicate installed-file contract entry")
required_unmanaged = contract.get("required_unmanaged_files")
if not isinstance(required_unmanaged, list) or any(not isinstance(item, str) for item in required_unmanaged):
    raise SystemExit("Invalid installed-file contract required_unmanaged_files")
for relative in required_unmanaged:
    if not (root / pathlib.PurePosixPath(relative)).is_file():
        print(f"Missing required unmanaged file: {relative}", file=sys.stderr)
        raise SystemExit(1)
for relative in sorted(required_managed - managed.keys()):
    print(f"Required installed file is not managed: {relative}", file=sys.stderr)
if required_managed - managed.keys():
    raise SystemExit(1)

override_set = set(overrides)
for relative in sorted(override_set - managed.keys()):
    print(f"Invalid local override: {relative}", file=sys.stderr)
if override_set - managed.keys():
    raise SystemExit(1)

failed = False
for relative, expected in sorted(managed.items()):
    if not isinstance(relative, str) or not isinstance(expected, str):
        print("Invalid managed file entry", file=sys.stderr)
        failed = True
        continue
    relative_path = pathlib.PurePosixPath(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        print(f"Invalid managed file path: {relative}", file=sys.stderr)
        failed = True
        continue
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        print(f"Invalid managed file hash: {relative}", file=sys.stderr)
        failed = True
        continue
    target = root / relative_path
    if not target.is_file():
        print(f"Missing managed file: {relative}", file=sys.stderr)
        failed = True
        continue
    resolved_target = target.resolve()
    if resolved_target != root and root not in resolved_target.parents:
        print(f"Managed file escapes installed root: {relative}", file=sys.stderr)
        failed = True
        continue
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if relative in override_set:
        print(f"Declared local override: {relative}")
    elif actual != expected:
        print(f"Managed file hash mismatch: {relative}", file=sys.stderr)
        failed = True

for schema_name in ("routing-decision.schema.json", "routing-receipt.schema.json"):
    schema_path = root / "schemas" / schema_name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid schema {schema_name}: {error}", file=sys.stderr)
        failed = True
        continue
    if not isinstance(schema, dict) or schema.get("type") != "object":
        print(f"Invalid schema root: {schema_name}", file=sys.stderr)
        failed = True

if failed:
    raise SystemExit(1)
PY

  python3 "$root/scripts/verify-routing.py"
  python3 -m unittest discover -s "$root/tests/installed" -v
  echo "CAPS installed layout verification passed."
}

if [[ -f "$root/install-manifest.json" ]]; then
  verify_installed_layout
  exit 0
fi

required_files=(
  "README.md"
  "AGENTS.md"
  "CONTEXT.md"
  "VERSION"
  "install.sh"
  "templates/AGENTS.caps-lane-factory.md"
  "templates/AGENTS.global.md"
  "templates/AGENTS.repo.md"
  "prompts/bootstrap-caps-conductor.md"
  "templates/adjacent-repo-link.md"
  "prompts/conductor.md"
  "prompts/adjacent-repo-router.md"
  "prompts/workers/implementation.md"
  "prompts/workers/research.md"
  "prompts/workers/qa.md"
  "prompts/workers/docs.md"
  "prompts/workers/review.md"
  "docs/setup-guide.md"
  "docs/naming-and-pinning.md"
  "docs/updates.md"
  "docs/conductor-workflow.md"
  "docs/gpt-5-6-routing.md"
  "docs/adr/0001-public-routing-engine-private-profile.md"
  "docs/operator-loop.md"
  "docs/evidence-and-handoffs.md"
  "docs/adjacent-repos.md"
  "docs/packs.md"
  "packs/README.md"
  "packs/_template/pack.yaml"
  "packs/_template/setup.md"
  "packs/_template/prompt-schedule.md"
  "packs/_template/skill-manifest.md"
  "packs/_template/lanes/conductor.md"
  "packs/_template/lanes/worker.md"
  "packs/full-circle-5/pack.yaml"
  "packs/full-circle-5/README.md"
  "packs/full-circle-5/setup.md"
  "packs/full-circle-5/prompt-schedule.md"
  "packs/full-circle-5/skill-manifest.md"
  "packs/full-circle-5/docs/daily-content-heartbeat.md"
  "packs/full-circle-5/automation/daily-content-heartbeat.toml"
  "packs/full-circle-5/lanes/mission-control.md"
  "packs/full-circle-5/lanes/build-lane.md"
  "packs/full-circle-5/lanes/daily-content-review.md"
  "examples/feature-build/README.md"
  "examples/release-check/README.md"
  "examples/routing/valid-luna.json"
  "examples/routing/valid-terra.json"
  "examples/routing/valid-sol-max.json"
  "examples/routing/valid-sol-ultra.json"
  "examples/routing/invalid-missing-authority.json"
  "examples/routing/routing-cases.json"
  "schemas/routing-decision.schema.json"
  "schemas/routing-receipt.schema.json"
  "scripts/verify-routing.py"
  "scripts/routing-receipt.py"
  "scripts/evaluate-routing-receipts.py"
  "scripts/title-sync-policy.py"
  "scripts/automation-doctor.py"
  "scripts/caps-update.py"
  "scripts/pinned-thread-snapshot.py"
  "scripts/build-release.py"
  "tests/installed/test_installed_commands.py"
  "config/installed-files.json"
  "config/title-preferences.json"
  "automations/pinned-title-sync/automation.toml"
  "automations/pinned-title-sync/prompt.md"
  "automations/caps-update/automation.toml"
  "automations/caps-update/prompt.md"
  "channels/stable.json"
)

missing=0
for file in "${required_files[@]}"; do
  if [[ ! -f "$root/$file" ]]; then
    echo "Missing: $file" >&2
    missing=1
  fi
done

if [[ ! -x "$root/install.sh" ]]; then
  echo "install.sh is not executable" >&2
  missing=1
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

bash -n "$root/install.sh"
bash -n "$root/scripts/verify.sh"
python3 - "$root" <<'PY'
import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("caps_update", root / "scripts/caps-update.py")
caps_update = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(caps_update)
contract = json.loads((root / "config/installed-files.json").read_text(encoding="utf-8"))
declared = contract.get("managed_files") if isinstance(contract, dict) else None
if contract.get("schema_version") != "1.0" or not isinstance(declared, list):
    raise SystemExit("Invalid installed-file contract")
actual = set(caps_update.release_managed_files(root))
expected = set(declared)
if len(expected) != len(declared):
    raise SystemExit("Duplicate installed-file contract entry")
for relative in sorted(actual - expected):
    print(f"Mapped file missing from installed-file contract: {relative}", file=sys.stderr)
for relative in sorted(expected - actual):
    print(f"Installed-file contract path is not mapped: {relative}", file=sys.stderr)
if actual != expected:
    raise SystemExit(1)
PY
python3 "$root/scripts/verify-routing.py"
python3 -m unittest discover -s "$root/tests" -v

receipt_tmp="$(mktemp -d)"
trap 'rm -rf "$receipt_tmp"' EXIT
receipt_id="$(python3 "$root/scripts/routing-receipt.py" --store "$receipt_tmp/receipts.jsonl" start --task-class coding --model gpt-5.6-sol --thinking medium --route-reason policy --quality-gate-id tests --task-snapshot-complete --profile-version test)"
python3 "$root/scripts/routing-receipt.py" --store "$receipt_tmp/receipts.jsonl" finish --receipt-id "$receipt_id" --outcome pass --delegation-quality complete --proof-ref tests >/dev/null
python3 "$root/scripts/evaluate-routing-receipts.py" --store "$receipt_tmp/receipts.jsonl" --output "$receipt_tmp/evaluation.json" >/dev/null
python3 - "$receipt_tmp" <<'PY'
import json
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
receipt = json.loads((root / "receipts.jsonl").read_text())
evaluation = json.loads((root / "evaluation.json").read_text())
assert receipt["quality_passed"] is True
assert evaluation["receipt_count"] == 1
assert receipt["schema_version"] == "1.1"
assert receipt["task_snapshot_complete"] is True
assert receipt["delegation_quality"] == "complete"
PY

python3 "$root/scripts/build-release.py" --output-dir "$receipt_tmp/release" >/dev/null
python3 - "$root" "$receipt_tmp/release" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
release_dir = pathlib.Path(sys.argv[2])
version = (root / "VERSION").read_text(encoding="utf-8").strip()
channel = json.loads((root / "channels/stable.json").read_text(encoding="utf-8"))
artifact = release_dir / f"caps-productivity-kit-{version}.tar.gz"
assert channel["version"] == version
assert channel["artifact_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
PY

for pack_dir in "$root"/packs/*; do
  [[ -d "$pack_dir" ]] || continue
  pack_name="$(basename "$pack_dir")"
  [[ "$pack_name" == "_template" ]] && continue

  for file in pack.yaml README.md setup.md prompt-schedule.md skill-manifest.md; do
    if [[ ! -f "$pack_dir/$file" ]]; then
      echo "Pack $pack_name missing: $file" >&2
      missing=1
    fi
  done

  if [[ ! -d "$pack_dir/lanes" ]]; then
    echo "Pack $pack_name missing: lanes/" >&2
    missing=1
  fi

  if ! grep -q '^id:' "$pack_dir/pack.yaml"; then
    echo "Pack $pack_name pack.yaml missing id" >&2
    missing=1
  fi

  if ! grep -q '^public_safe:' "$pack_dir/pack.yaml"; then
    echo "Pack $pack_name pack.yaml missing public_safe" >&2
    missing=1
  fi

  if ! grep -q '^status:' "$pack_dir/pack.yaml"; then
    echo "Pack $pack_name pack.yaml missing status" >&2
    missing=1
  fi
done

private_pattern='019e[0-9a-f-]{20,}|source_thread_id|sk_live_|sk_test_|gho_[A-Za-z0-9_]+|api[_-]?key[:=]|secret[_-]?key[:=]'
scan_private_material() {
  if command -v rg >/dev/null 2>&1; then
    rg -n "$private_pattern" "$root/packs"
  else
    grep -REn "$private_pattern" "$root/packs"
  fi
}

if scan_private_material >/dev/null; then
  echo "Potential private or secret material found in packs/" >&2
  scan_private_material >&2
  missing=1
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

echo "CAPS kit verification passed."
