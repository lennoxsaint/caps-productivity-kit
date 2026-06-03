#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh /path/to/project [--pack pack-name] [--no-open] [--no-agents-update]

Copies CAPS templates into an existing project.

What it writes:
  AGENTS.md       created or updated with a managed CAPS block unless disabled
  .caps/          prompts, templates, docs, examples, bootstrap, and selected packs

Existing AGENTS.md files get a timestamped backup before managed block updates.
Packs are copied only when requested with --pack.
Codex Desktop is opened by default when the `codex` CLI is available.
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
open_codex=true
update_agents=true
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
    --no-open)
      open_codex=false
      shift
      ;;
    --no-agents-update)
      update_agents=false
      shift
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
mkdir -p "$caps_dir/bootstrap"
cp "$script_dir/prompts/bootstrap-caps-conductor.md" "$caps_dir/bootstrap/start-caps-conductor.md"

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

managed_block_source="$script_dir/templates/AGENTS.caps-lane-factory.md"
agents_file="$target_dir/AGENTS.md"

update_managed_block() {
  local file="$1"
  local block_file="$2"
  local tmp_file="$file.tmp.$$"
  local start_marker="<!-- BEGIN CAPS MANAGED: lane-factory -->"
  local end_marker="<!-- END CAPS MANAGED: lane-factory -->"

  awk -v start="$start_marker" -v end="$end_marker" -v block_file="$block_file" '
    BEGIN {
      while ((getline line < block_file) > 0) {
        block = block line "\n"
      }
      close(block_file)
      in_block = 0
      replaced = 0
    }
    $0 == start {
      if (!replaced) {
        printf "%s", block
        replaced = 1
      }
      in_block = 1
      next
    }
    $0 == end {
      in_block = 0
      next
    }
    !in_block {
      print
    }
    END {
      if (!replaced) {
        if (NR > 0) {
          print ""
        }
        printf "%s", block
      }
    }
  ' "$file" > "$tmp_file"

  mv "$tmp_file" "$file"
}

if [[ "$update_agents" == true ]]; then
  if [[ -f "$agents_file" ]]; then
    backup_file="$target_dir/AGENTS.md.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$agents_file" "$backup_file"
    update_managed_block "$agents_file" "$managed_block_source"
    echo "Updated AGENTS.md managed CAPS block"
    echo "Backup: $backup_file"
  else
    cp "$script_dir/templates/AGENTS.repo.md" "$agents_file"
    update_managed_block "$agents_file" "$managed_block_source"
    echo "Created AGENTS.md with managed CAPS block"
  fi
else
  echo "Skipped AGENTS.md update"
  echo "Suggested manual sources:"
  echo "  $caps_dir/templates/AGENTS.repo.md"
  echo "  $caps_dir/templates/AGENTS.caps-lane-factory.md"
fi

if [[ "$open_codex" == true ]]; then
  if command -v codex >/dev/null 2>&1; then
    if codex app "$target_dir" >/dev/null 2>&1; then
      echo "Opened Codex Desktop for: $target_dir"
    else
      echo "Could not open Codex Desktop automatically. Run: codex app \"$target_dir\"" >&2
    fi
  else
    echo "Codex CLI not found. Open this project in Codex Desktop manually." >&2
  fi
fi

if [[ "$update_agents" == true ]]; then
  agents_next_step="Review $target_dir/AGENTS.md and fill in real project commands and safety rules."
else
  agents_next_step="Merge .caps/templates/AGENTS.repo.md and .caps/templates/AGENTS.caps-lane-factory.md into your project instructions when ready."
fi

cat <<EOF

CAPS installed in:
  $target_dir

Next:
  1. $agents_next_step
  2. In Codex, run the bootstrap prompt:

     Read .caps/bootstrap/start-caps-conductor.md and execute it.

     The bootstrap creates and pins CAPS CONDUCTOR when the active Codex runtime
     exposes safe thread-control tools. If those tools are unavailable, it gives
     exact manual-mode steps instead of pretending automation worked.
EOF

if [[ -n "$pack_name" ]]; then
  cat <<EOF
  3. Review the installed pack:

     .caps/packs/$pack_name/setup.md

     Packs provide prompts, lane templates, and checklists. Shell install does
     not create, pin, rename, send, deploy, or publish anything; the Conductor
     may use safe thread-control tools later when your Codex runtime exposes them.
EOF
fi
