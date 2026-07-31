#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
  "scripts/caps-update.py"
  "scripts/build-release.py"
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
