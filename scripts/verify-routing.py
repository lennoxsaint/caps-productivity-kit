#!/usr/bin/env python3
"""Dependency-free contract checks for the public CAPS routing examples."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/routing-decision.schema.json").read_text())
REQUIRED = set(SCHEMA["required"])
AUTH_REQUIRED = set(SCHEMA["properties"]["authority"]["required"])
MODELS = set(SCHEMA["properties"]["model"]["enum"])
THINKING = set(SCHEMA["properties"]["thinking"]["enum"])
TASK_CLASSES = set(SCHEMA["properties"]["task_class"]["enum"])


def validate(decision: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED - decision.keys()
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
    if decision.get("model") not in MODELS:
        errors.append("invalid model")
    if decision.get("thinking") not in THINKING:
        errors.append("invalid thinking")
    if decision.get("task_class") not in TASK_CLASSES:
        errors.append("invalid task_class")
    if not isinstance(decision.get("escalate_when"), list) or not decision.get("escalate_when"):
        errors.append("escalate_when must be a non-empty list")
    authority = decision.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        missing_authority = AUTH_REQUIRED - authority.keys()
        if missing_authority:
            errors.append(f"missing authority fields: {sorted(missing_authority)}")
        for field in AUTH_REQUIRED:
            value = authority.get(field)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                errors.append(f"authority.{field} must be a non-empty string list")
    return errors


def main() -> None:
    example_dir = ROOT / "examples/routing"
    for path in sorted(example_dir.glob("valid-*.json")):
        errors = validate(json.loads(path.read_text()))
        if errors:
            raise SystemExit(f"{path.name} should be valid: {errors}")

    invalid = json.loads((example_dir / "invalid-missing-authority.json").read_text())
    if not validate(invalid):
        raise SystemExit("invalid-missing-authority.json unexpectedly passed")

    expected = {
        "mechanical extraction": ("gpt-5.6-luna", "low"),
        "frozen plan implementation": ("gpt-5.6-terra", "medium"),
        "ambiguous architecture": ("gpt-5.6-sol", "high"),
        "indivisible hardest problem": ("gpt-5.6-sol", "max"),
        "independent high value lanes": ("gpt-5.6-sol", "ultra"),
    }
    cases = json.loads((example_dir / "routing-cases.json").read_text())
    actual = {case["name"]: (case["model"], case["thinking"]) for case in cases}
    if actual != expected:
        raise SystemExit(f"routing cases differ: {actual!r}")

    print("CAPS routing verification passed.")


if __name__ == "__main__":
    main()
