#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_files=(
  "README.md"
  "AGENTS.md"
  "install.sh"
  "templates/AGENTS.global.md"
  "templates/AGENTS.repo.md"
  "prompts/conductor.md"
  "prompts/workers/implementation.md"
  "prompts/workers/research.md"
  "prompts/workers/qa.md"
  "prompts/workers/docs.md"
  "prompts/workers/review.md"
  "docs/setup-guide.md"
  "docs/naming-and-pinning.md"
  "docs/conductor-workflow.md"
  "docs/operator-loop.md"
  "docs/evidence-and-handoffs.md"
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
