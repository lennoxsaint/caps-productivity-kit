#!/usr/bin/env python3
"""Dependency-free contract checks for the public CAPS routing examples."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/routing-decision.schema.json").read_text())
REQUIRED = set(SCHEMA["required"])
SNAPSHOT_REQUIRED = set(SCHEMA["properties"]["task_snapshot"]["required"])
AUTH_REQUIRED = set(SCHEMA["properties"]["authority"]["required"])
MODELS = set(SCHEMA["properties"]["model"]["enum"])
THINKING = set(SCHEMA["properties"]["thinking"]["enum"])
ESCALATION_THINKING = set(SCHEMA["properties"]["escalation_route"]["properties"]["thinking"]["enum"])
TASK_CLASSES = set(SCHEMA["properties"]["task_class"]["enum"])
EVIDENCE_STATES = set(SCHEMA["properties"]["evidence_state"]["enum"])


def validate(decision: dict) -> list[str]:
    errors: list[str] = []
    unknown = decision.keys() - SCHEMA["properties"].keys()
    if unknown:
        errors.append(f"unknown top-level fields: {sorted(unknown)}")
    missing = REQUIRED - decision.keys()
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
    snapshot = decision.get("task_snapshot")
    if not isinstance(snapshot, dict):
        errors.append("task_snapshot must be an object")
    else:
        missing_snapshot = SNAPSHOT_REQUIRED - snapshot.keys()
        if missing_snapshot:
            errors.append(f"missing task_snapshot fields: {sorted(missing_snapshot)}")
        unknown_snapshot = snapshot.keys() - SCHEMA["properties"]["task_snapshot"]["properties"].keys()
        if unknown_snapshot:
            errors.append(f"unknown task_snapshot fields: {sorted(unknown_snapshot)}")
        if not isinstance(snapshot.get("objective"), str) or not snapshot.get("objective"):
            errors.append("task_snapshot.objective must be a non-empty string")
        for field in ("scope", "acceptance_criteria", "stop_conditions"):
            value = snapshot.get(field)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                errors.append(f"task_snapshot.{field} must be a non-empty string list")
        if snapshot.get("risk_level") not in {"low", "medium", "high"}:
            errors.append("invalid task_snapshot.risk_level")
        if snapshot.get("side_effects") not in {"none", "local_reversible", "external_reversible", "irreversible"}:
            errors.append("invalid task_snapshot.side_effects")
        evidence_refs = snapshot.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not all(
            isinstance(item, str) and item for item in evidence_refs
        ):
            errors.append("task_snapshot.evidence_refs must be a string list")
    if decision.get("model") not in MODELS:
        errors.append("invalid model")
    if decision.get("thinking") not in THINKING:
        errors.append("invalid thinking")
    if decision.get("task_class") not in TASK_CLASSES:
        errors.append("invalid task_class")
    for field in ("rationale", "quality_gate"):
        if not isinstance(decision.get(field), str) or not decision.get(field):
            errors.append(f"{field} must be a non-empty string")
    if decision.get("evidence_state") not in EVIDENCE_STATES:
        errors.append("invalid evidence_state")
    if decision.get("routing_mode") not in {"direct", "probe_then_escalate"}:
        errors.append("invalid routing_mode")
    if decision.get("execution_level") not in {"root", "worker"}:
        errors.append("invalid execution_level")
    if decision.get("thinking") == "ultra" and decision.get("execution_level") != "root":
        errors.append("ultra is root-only")
    if decision.get("model") == "gpt-5.6-terra" and decision.get("evidence_state") not in {
        "personal_eval", "runtime_observation"
    }:
        errors.append("terra requires personalized or runtime evidence")
    if decision.get("model") == "gpt-5.6-terra":
        calibration = decision.get("calibration")
        if not isinstance(calibration, dict):
            errors.append("terra requires calibration evidence")
        else:
            compared = set(calibration.get("compared_models", []))
            if not {"gpt-5.6-luna", "gpt-5.6-sol"}.issubset(compared):
                errors.append("terra calibration must compare Luna and Sol")
            if calibration.get("runs_per_candidate", 0) < 3:
                errors.append("terra calibration requires at least three runs per candidate")
            if calibration.get("metric") != "verified_completions_per_minute":
                errors.append("terra calibration must use verified completions per minute")
            if not calibration.get("receipt"):
                errors.append("terra calibration requires a receipt")
            if calibration.keys() - {"receipt", "compared_models", "runs_per_candidate", "metric"}:
                errors.append("unknown calibration fields")
    if decision.get("routing_mode") == "probe_then_escalate":
        escalation = decision.get("escalation_route")
        if not isinstance(escalation, dict):
            errors.append("probe_then_escalate requires escalation_route")
        elif escalation.get("model") not in MODELS or escalation.get("thinking") not in ESCALATION_THINKING:
            errors.append("invalid escalation_route")
        elif escalation.keys() - {"model", "thinking"}:
            errors.append("unknown escalation_route fields")
    if not isinstance(decision.get("escalate_when"), list) or not decision.get("escalate_when"):
        errors.append("escalate_when must be a non-empty list")
    authority = decision.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        missing_authority = AUTH_REQUIRED - authority.keys()
        if missing_authority:
            errors.append(f"missing authority fields: {sorted(missing_authority)}")
        unknown_authority = authority.keys() - SCHEMA["properties"]["authority"]["properties"].keys()
        if unknown_authority:
            errors.append(f"unknown authority fields: {sorted(unknown_authority)}")
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

    for path in sorted(example_dir.glob("invalid-*.json")):
        if not validate(json.loads(path.read_text())):
            raise SystemExit(f"{path.name} unexpectedly passed")

    expected = {
        "mechanical extraction": ("gpt-5.6-luna", "low"),
        "frozen plan implementation": ("gpt-5.6-luna", "high"),
        "integration-sensitive implementation": ("gpt-5.6-sol", "medium"),
        "evidence-gated middle route": ("gpt-5.6-terra", "high"),
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
