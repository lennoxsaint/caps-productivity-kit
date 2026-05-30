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
  "docs/evidence-and-handoffs.md"
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

echo "CAPS kit verification passed."
