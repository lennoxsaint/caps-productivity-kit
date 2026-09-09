#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh /path/to/project [--pack pack-name] [--no-open] [--no-agents-update] [--config-scope project|global]

Copies CAPS templates into an existing project.

What it writes:
  AGENTS.md       created or updated with a managed CAPS block unless disabled
  .caps/          prompts, templates, docs, schemas, examples, bootstrap, and selected packs
  .codex/config.toml  created with safe defaults only when the project config is missing

Existing AGENTS.md files get a timestamped backup before managed block updates.
Existing Codex configs are validated and preserved byte-for-byte.
A target named .codex uses config.toml directly; --config-scope can select this
behavior explicitly for a custom global config directory.
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
config_scope=auto
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
    --config-scope)
      config_scope="${2:-}"
      if [[ "$config_scope" != project && "$config_scope" != global ]]; then
        echo "--config-scope requires project or global" >&2
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
codex_config_path="$target_dir/.codex/config.toml"
if [[ "$config_scope" == global || ( "$config_scope" == auto && "$(basename "$target_dir")" == .codex ) ]]; then
  codex_config_path="$target_dir/config.toml"
fi

# Validate owner-managed Codex configuration before writing any installation
# files. A missing project config receives the helper's explicit fresh-install
# defaults; an existing config is parse-checked only and never upgraded.
if [[ -L "$codex_config_path" && ! -e "$codex_config_path" ]]; then
  echo "Codex config symlink target does not exist: $codex_config_path" >&2
  exit 1
fi
if [[ -e "$codex_config_path" || -L "$codex_config_path" ]]; then
  python3 "$script_dir/scripts/codex-config.py" \
    --config "$codex_config_path" plan >/dev/null
  echo "Validated existing Codex config: $codex_config_path"
else
  python3 "$script_dir/scripts/codex-config.py" \
    --config "$codex_config_path" apply --expected-hash missing >/dev/null
  echo "Created Codex config: $codex_config_path"
fi

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

mkdir -p "$caps_dir/defaults" "$caps_dir/config"
if [[ ! -f "$caps_dir/config/title-preferences.json" ]]; then
  cp "$script_dir/config/title-preferences.json" "$caps_dir/config/title-preferences.json"
  echo "Created title preferences: $caps_dir/config/title-preferences.json"
else
  echo "Preserved title preferences: $caps_dir/config/title-preferences.json"
fi
mkdir -p "$caps_dir/bootstrap"
mkdir -p "$caps_dir/state"
if [[ ! -e "$caps_dir/state/.gitignore" ]]; then
cat > "$caps_dir/state/.gitignore" <<'EOF'
*
!.gitignore
EOF
fi

python3 - "$caps_dir" "$script_dir" <<'PY'
import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys
from datetime import datetime, timezone

caps = pathlib.Path(sys.argv[1])
source_root = pathlib.Path(sys.argv[2])
contract = json.loads((source_root / "scripts/install-contract.json").read_text(encoding="utf-8"))
source_mappings = contract.get("source_mappings")
if not isinstance(source_mappings, dict):
    raise SystemExit("Invalid installed-file contract source_mappings")
spec = importlib.util.spec_from_file_location("caps_installer_update", source_root / "scripts/caps-update.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
manifest_path = caps / "install-manifest.json"
previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
expected = previous.get("managed_files", {})
if not isinstance(expected, dict):
    raise SystemExit("Invalid existing install manifest")
backup = caps / "state/install-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
if manifest_path.exists():
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(manifest_path, backup / "install-manifest.json")
managed = {}
preserved = []

def install_file(source, relative):
    target = caps / relative
    incoming = hashlib.sha256(source.read_bytes()).hexdigest()
    managed[str(relative)] = incoming
    if target.exists():
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if current == incoming:
            return
        if expected.get(str(relative)) != current:
            preserved.append(str(relative))
            return
        destination = backup / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
    updater.atomic_copy(source, target)

for source_name, target_name in source_mappings.items():
    source = source_root / source_name
    if source.is_file():
        install_file(source, pathlib.Path(target_name))
        continue
    for source_path in sorted(source.rglob("*")):
        if source_path.is_file() and "__pycache__" not in source_path.parts and source_path.suffix != ".pyc":
            relative = pathlib.Path(target_name) / source_path.relative_to(source)
            install_file(source_path, relative)
manifest = {
    "schema_version": "1.0",
    "version": (source_root / "VERSION").read_text(encoding="utf-8").strip(),
    "channel": "stable",
    "source_repository": "https://github.com/lennoxsaint/caps-productivity-kit",
    "managed_files": managed,
    "local_overrides": sorted(preserved),
    "installed_at": datetime.now(timezone.utc).isoformat(),
}
updater.atomic_json(manifest_path, manifest)
PY

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
  3. Review the paused automation templates:

     $caps_dir/automations/pinned-title-sync/automation.toml
     $caps_dir/automations/caps-update/automation.toml

     Generate the project-specific native activation prompt:

     python3 "$caps_dir/scripts/automation-doctor.py" \
       --project "$target_dir" activation

     Give that output to Codex. It uses absolute prompt paths and asks the
     native Scheduled task controls to upsert, activate, and read back both
     jobs. The title sync uses a twenty-minute fallback; the stable updater
     checks daily and preserves local overrides. If native controls are absent,
     CAPS reports the activation blocker and does not touch Codex registry
     files directly.
EOF

if [[ -n "$pack_name" ]]; then
  cat <<EOF
  4. Review the installed pack:

     .caps/packs/$pack_name/setup.md

     Packs provide prompts, lane templates, and checklists. Shell install does
     not create, pin, rename, send, deploy, or publish anything; the Conductor
     may use safe thread-control tools later when your Codex runtime exposes them.
EOF
fi
