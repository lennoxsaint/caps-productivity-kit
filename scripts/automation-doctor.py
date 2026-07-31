#!/usr/bin/env python3
"""Inspect CAPS automation readiness and emit a native activation prompt."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any


AUTOMATIONS: dict[str, dict[str, str]] = {
    "caps-pinned-title-sync": {
        "directory": "pinned-title-sync",
        "kind": "cron",
        "name": "CAPS pinned title sync",
        "rrule": "RRULE:FREQ=MINUTELY;INTERVAL=20",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
    },
    "caps-stable-update": {
        "directory": "caps-update",
        "kind": "cron",
        "name": "CAPS stable update",
        "rrule": "RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
    },
}


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected TOML table: {path}")
    return value


def normalize_rrule(value: object) -> str:
    text = str(value or "")
    return text if text.startswith("RRULE:") else f"RRULE:{text}"


def template_mismatches(
    automation_id: str,
    template: dict[str, Any],
    prompt_path: Path,
) -> list[str]:
    spec = AUTOMATIONS[automation_id]
    checks = {
        "id": template.get("id") == automation_id,
        "kind": template.get("kind") == spec["kind"],
        "name": template.get("name") == spec["name"],
        "status": template.get("status") == "PAUSED",
        "rrule": normalize_rrule(template.get("rrule")) == spec["rrule"],
        "model": template.get("model") == spec["model"],
        "reasoning_effort": template.get("reasoning_effort") == spec["reasoning_effort"],
        "execution_environment": template.get("execution_environment") == "local",
        "target": isinstance(template.get("target"), dict)
        and template["target"].get("type") == "project",
        "prompt_file": prompt_path.is_file(),
    }
    return [field for field, valid in checks.items() if not valid]


def native_mismatches(
    automation_id: str,
    native: dict[str, Any],
    project: Path,
    prompt_path: Path,
) -> list[str]:
    spec = AUTOMATIONS[automation_id]
    target = native.get("target")
    cwds = native.get("cwds")
    checks = {
        "id": native.get("id") == automation_id,
        "kind": native.get("kind") == spec["kind"],
        "name": native.get("name") == spec["name"],
        "status": native.get("status") == "ACTIVE",
        "rrule": normalize_rrule(native.get("rrule")) == spec["rrule"],
        "model": native.get("model") == spec["model"],
        "reasoning_effort": native.get("reasoning_effort") == spec["reasoning_effort"],
        "execution_environment": native.get("execution_environment") == "local",
        "target": isinstance(target, dict)
        and target.get("type") == "project"
        and bool(target.get("project_id")),
        "cwd": isinstance(cwds, list)
        and str(project) in {str(Path(str(value)).resolve()) for value in cwds},
        "prompt": str(prompt_path) in str(native.get("prompt", "")),
    }
    return [field for field, valid in checks.items() if not valid]


def inspect_automations(project: Path, native_root: Path) -> dict[str, Any]:
    project = project.resolve()
    native_root = native_root.expanduser().resolve()
    results: list[dict[str, Any]] = []
    for automation_id, spec in AUTOMATIONS.items():
        installed_dir = project / ".caps/automations" / spec["directory"]
        template_path = installed_dir / "automation.toml"
        prompt_path = installed_dir / "prompt.md"
        template_errors: list[str] = []
        if not template_path.is_file():
            template_errors.append("automation_file")
        else:
            try:
                template_errors.extend(
                    template_mismatches(
                        automation_id,
                        read_toml(template_path),
                        prompt_path,
                    )
                )
            except (OSError, tomllib.TOMLDecodeError, ValueError):
                template_errors.append("automation_toml")

        native_path = native_root / automation_id / "automation.toml"
        mismatches: list[str] = []
        if template_errors:
            native_status = "template_invalid"
        elif not native_path.is_file():
            native_status = "missing"
        else:
            try:
                mismatches = native_mismatches(
                    automation_id,
                    read_toml(native_path),
                    project,
                    prompt_path,
                )
                native_status = "drift" if mismatches else "active"
            except (OSError, tomllib.TOMLDecodeError, ValueError):
                native_status = "invalid"
                mismatches = ["automation_toml"]

        results.append(
            {
                "id": automation_id,
                "template": str(template_path),
                "template_errors": template_errors,
                "native": str(native_path),
                "native_status": native_status,
                "mismatches": mismatches,
            }
        )

    statuses = {item["native_status"] for item in results}
    if statuses == {"active"}:
        status = "active"
    elif "template_invalid" in statuses:
        status = "template_invalid"
    elif statuses & {"drift", "invalid"}:
        status = "drift"
    else:
        status = "registration_required"
    return {
        "schema_version": "1.0",
        "status": status,
        "project": str(project),
        "native_registry": str(native_root),
        "automations": results,
    }


def activation_prompt(project: Path) -> str:
    project = project.resolve()
    title_prompt = (
        project / ".caps/automations/pinned-title-sync/prompt.md"
    )
    update_prompt = project / ".caps/automations/caps-update/prompt.md"
    return f"""Use native Scheduled task controls to create or update the two CAPS
automations below for this project. Never edit Codex registry files, databases,
or session indexes directly. Match an existing task by ID and update it in
place; do not create duplicates.

Project working directory: {project}
Execution environment: local

1. CAPS pinned title sync
   ID: caps-pinned-title-sync
   Kind: cron
   Status: ACTIVE
   Schedule: RRULE:FREQ=MINUTELY;INTERVAL=20
   Model: gpt-5.6-luna
   Reasoning effort: low
   Prompt: Read {title_prompt} and execute it exactly. This automation updates
   coordination metadata only; titles are never execution proof.

2. CAPS stable update
   ID: caps-stable-update
   Kind: cron
   Status: ACTIVE
   Schedule: RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0
   Model: gpt-5.6-luna
   Reasoning effort: low
   Prompt: Read {update_prompt} and execute it exactly. Apply only verified,
   compatible, non-disruptive stable updates; preserve local configuration,
   data, and overrides.

Before activation, confirm both prompt files exist and validate each prompt
manually without mutating thread titles or applying an update. After the native
create/update calls, read back each task's ID, status, schedule, model,
reasoning effort, execution environment, project target, and working directory.
Report native_automation_controls_unavailable and make no changes if the
runtime does not expose native Scheduled task controls. A copied TOML template
is not proof that a task is active.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument(
        "--native-root",
        type=Path,
        default=Path.home() / ".codex/automations",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")
    subparsers.add_parser("activation")
    args = parser.parse_args()

    if args.command == "activation":
        print(activation_prompt(args.project))
        return

    report = inspect_automations(args.project, args.native_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "active":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
