#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh /path/to/project [--pack pack-name]

Copies CAPS templates into an existing project.

What it writes:
  AGENTS.md       if one does not already exist
  .caps/          prompts, templates, docs, examples, and selected packs

Existing AGENTS.md files are not overwritten.
Packs are copied only when requested with --pack.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

target="${1:-}"
if [[ -z "$target" ]]; then
  usage
  exit 1
fi

pack_name=""
shift || true
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --pack)
      pack_name="${2:-}"
      if [[ -z "$pack_name" ]]; then
        echo "--pack requires a pack name" >&2
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$target" ]]; then
  echo "Target directory does not exist: $target" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_dir="$(cd "$target" && pwd)"
caps_dir="$target_dir/.caps"

mkdir -p "$caps_dir"

copy_dir() {
  local from="$1"
  local to="$2"
  mkdir -p "$to"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "$from"/ "$to"/
  else
    cp -R "$from"/. "$to"/
  fi
}

copy_dir "$script_dir/prompts" "$caps_dir/prompts"
copy_dir "$script_dir/templates" "$caps_dir/templates"
copy_dir "$script_dir/docs" "$caps_dir/docs"
copy_dir "$script_dir/examples" "$caps_dir/examples"

if [[ -n "$pack_name" ]]; then
  if [[ ! -d "$script_dir/packs/$pack_name" ]]; then
    echo "Pack does not exist: $pack_name" >&2
    echo "Available packs:" >&2
    find "$script_dir/packs" -mindepth 1 -maxdepth 1 -type d ! -name "_template" -exec basename {} \; | sort >&2
    exit 1
  fi
  mkdir -p "$caps_dir/packs"
  copy_dir "$script_dir/packs/$pack_name" "$caps_dir/packs/$pack_name"
  echo "Installed pack: $pack_name"
fi

if [[ -f "$target_dir/AGENTS.md" ]]; then
  echo "Kept existing AGENTS.md"
  echo "Suggested merge source: $caps_dir/templates/AGENTS.repo.md"
else
  cp "$script_dir/templates/AGENTS.repo.md" "$target_dir/AGENTS.md"
  echo "Created AGENTS.md"
fi

cat <<EOF

CAPS installed in:
  $target_dir

Next:
  1. Edit $target_dir/AGENTS.md with your real project commands and safety rules.
  2. Start a Codex conductor thread with:

     Use .caps/prompts/conductor.md as the operating prompt for this workspace.
     Read AGENTS.md first, then help me plan and execute the next project slice.
EOF

if [[ -n "$pack_name" ]]; then
  cat <<EOF
  3. Review the installed pack:

     .caps/packs/$pack_name/setup.md

     Packs provide prompts and checklists only. They do not automatically create,
     pin, rename, send, deploy, or publish anything.
EOF
fi
