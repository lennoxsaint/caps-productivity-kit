#!/usr/bin/env python3
"""Dependency-free checks for capability-bound CAPS routing decisions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/routing-decision.schema.json").read_text(encoding="utf-8"))
REQUIRED = set(SCHEMA["required"])
SNAPSHOT_REQUIRED = set(SCHEMA["properties"]["task_snapshot"]["required"])
AUTH_REQUIRED = set(SCHEMA["properties"]["authority"]["required"])
TASK_CLASSES = set(SCHEMA["properties"]["task_class"]["enum"])
EVIDENCE_STATES = set(SCHEMA["properties"]["evidence_state"]["enum"])
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_WORKER_ACTIONS = {"read", "analyze", "test", "local_reversible_edit"}
REQUIRED_WORKER_PROHIBITIONS = {
    "external_send",
    "production_write",
    "merge",
    "deploy",
    "publish",
    "credential_change",
    "irreversible_action",
    "authority_widening",
}
RUNTIME_CAPABILITY_SOURCE = "codex-runtime-model-catalog"
FIXTURE_CAPABILITY_SOURCE = "caps-test-fixture"


def capability_digest(snapshot: dict[str, Any]) -> str:
    payload = {key: value for key, value in snapshot.items() if key != "digest"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def supported_route(capabilities: dict[str, Any], model_id: Any, thinking: Any) -> dict[str, Any] | None:
    for model in capabilities.get("models", []):
        if model.get("id") == model_id and thinking in model.get("reasoning_levels", []):
            return model
    return None


def valid_string_list(value: Any, *, nonempty: bool = True) -> bool:
    return isinstance(value, list) and (bool(value) or not nonempty) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def validate(
    decision: dict[str, Any],
    capabilities: dict[str, Any] | None = None,
    *,
    allow_test_fixture: bool = False,
    now: datetime | None = None,
    max_snapshot_age_seconds: int = 300,
) -> list[str]:
    errors: list[str] = []
    unknown = decision.keys() - SCHEMA["properties"].keys()
    if unknown:
        errors.append(f"unknown top-level fields: {sorted(unknown)}")
    missing = REQUIRED - decision.keys()
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")

    task_snapshot = decision.get("task_snapshot")
    if not isinstance(task_snapshot, dict):
        errors.append("task_snapshot must be an object")
        task_snapshot = {}
    else:
        missing_snapshot = SNAPSHOT_REQUIRED - task_snapshot.keys()
        if missing_snapshot:
            errors.append(f"missing task_snapshot fields: {sorted(missing_snapshot)}")
        unknown_snapshot = task_snapshot.keys() - SCHEMA["properties"]["task_snapshot"]["properties"].keys()
        if unknown_snapshot:
            errors.append(f"unknown task_snapshot fields: {sorted(unknown_snapshot)}")
    if not isinstance(task_snapshot.get("objective"), str) or not task_snapshot.get("objective"):
        errors.append("task_snapshot.objective must be a non-empty string")
    for field in ("scope", "acceptance_criteria", "stop_conditions"):
        if not valid_string_list(task_snapshot.get(field)):
            errors.append(f"task_snapshot.{field} must be a non-empty string list")
    if task_snapshot.get("risk_level") not in {"low", "medium", "high"}:
        errors.append("invalid task_snapshot.risk_level")
    if task_snapshot.get("side_effects") not in {"none", "local_reversible", "external_reversible", "irreversible"}:
        errors.append("invalid task_snapshot.side_effects")
    if not valid_string_list(task_snapshot.get("evidence_refs"), nonempty=False):
        errors.append("task_snapshot.evidence_refs must be a string list")

    if decision.get("task_class") not in TASK_CLASSES:
        errors.append("invalid task_class")
    for field in ("requested_model", "requested_thinking", "resolved_model", "resolved_thinking"):
        if not isinstance(decision.get(field), str) or not decision.get(field):
            errors.append(f"{field} must be a non-empty string")
    if decision.get("model") is not None and decision.get("model") != decision.get("resolved_model"):
        errors.append("legacy model alias must equal resolved_model")
    if decision.get("thinking") is not None and decision.get("thinking") != decision.get("resolved_thinking"):
        errors.append("legacy thinking alias must equal resolved_thinking")
    route_differs = (decision.get("requested_model"), decision.get("requested_thinking")) != (
        decision.get("resolved_model"), decision.get("resolved_thinking")
    )
    route_resolution = decision.get("route_resolution")
    if route_differs:
        if not isinstance(route_resolution, dict) or set(route_resolution) != {"reason", "limitation"}:
            errors.append("an explicit route_resolution is required when requested and resolved routes differ")
        elif route_resolution.get("reason") not in {"unsupported_model", "unsupported_effort", "not_live", "not_entitled", "policy_blocked"} or not isinstance(route_resolution.get("limitation"), str) or not route_resolution.get("limitation"):
            errors.append("route_resolution must record a valid reason and non-empty limitation")
    elif route_resolution is not None:
        errors.append("route_resolution is only valid when requested and resolved routes differ")

    digest = decision.get("capability_snapshot_digest")
    if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        errors.append("capability_snapshot_digest must be sha256:<64 lowercase hex characters>")
    if capabilities is None:
        errors.append("a runtime capability snapshot is required before spawn")
    else:
        source = capabilities.get("source")
        if source == FIXTURE_CAPABILITY_SOURCE:
            if not allow_test_fixture:
                errors.append("test fixture capability snapshots cannot authorize live routing")
        elif source != RUNTIME_CAPABILITY_SOURCE:
            errors.append(f"live routing requires source={RUNTIME_CAPABILITY_SOURCE}")
        else:
            try:
                captured_at = datetime.fromisoformat(str(capabilities.get("captured_at", "")).replace("Z", "+00:00"))
                if captured_at.tzinfo is None:
                    raise ValueError
                current = now or datetime.now(timezone.utc)
                age = (current - captured_at.astimezone(timezone.utc)).total_seconds()
                if age < -30:
                    errors.append("runtime capability snapshot is from the future")
                elif age > max_snapshot_age_seconds:
                    errors.append("runtime capability snapshot is stale")
            except ValueError:
                errors.append("captured_at must be an RFC 3339 timestamp with timezone")
        actual_digest = capability_digest(capabilities)
        if capabilities.get("digest") != actual_digest:
            errors.append("supplied capability snapshot has an invalid digest")
        if digest != actual_digest:
            errors.append("capability_snapshot_digest does not match the supplied snapshot")
        requested = supported_route(capabilities, decision.get("requested_model"), decision.get("requested_thinking"))
        resolved = supported_route(capabilities, decision.get("resolved_model"), decision.get("resolved_thinking"))
        requested_eligible = requested is not None and all(
            requested.get(field) is True for field in ("live", "entitled", "allowed_by_policy")
        )
        if requested is None and not route_differs:
            errors.append("requested route is not supported by the capability snapshot")
        if resolved is None:
            errors.append("resolved route is not supported by the capability snapshot")
        if route_differs and requested_eligible:
            errors.append("explicit rerouting is allowed only when the requested route is unavailable or blocked")
        for label, model in (("resolved", resolved),):
            if model is None:
                continue
            if not model.get("live") or not model.get("entitled") or not model.get("allowed_by_policy"):
                errors.append(f"{label} route must be live, entitled, and allowed by policy")
            specialist_classes = model.get("specialist_task_classes", [])
            if str(model.get("provider", "")).lower() == "daybreak":
                if not model.get("live") or not model.get("entitled") or not model.get("allowed_by_policy"):
                    errors.append("Daybreak route must be live, entitled, and allowed by policy")
            if specialist_classes and decision.get("task_class") not in specialist_classes:
                errors.append("specialist route must match an advertised specialist task class")

    if decision.get("routing_mode") not in {"direct", "probe_then_escalate"}:
        errors.append("invalid routing_mode")
    if decision.get("evidence_state") not in EVIDENCE_STATES:
        errors.append("invalid evidence_state")
    if decision.get("execution_level") not in {"root", "worker"}:
        errors.append("invalid execution_level")
    if decision.get("worker_kind") not in {"subagent", "durable_thread"}:
        errors.append("invalid worker_kind")
    fork_turns = decision.get("fork_turns")
    if not isinstance(fork_turns, str) or not re.fullmatch(r"none|all|[1-9][0-9]*", fork_turns):
        errors.append("fork_turns must be none, all, or a positive integer string")
    depth = decision.get("delegation_depth")
    if not isinstance(depth, int) or isinstance(depth, bool) or not 0 <= depth <= 2:
        errors.append("delegation_depth must be between 0 and 2")
    if not isinstance(decision.get("nested_delegation"), bool):
        errors.append("nested_delegation must be explicitly true or false")
    if depth == 2 and decision.get("nested_delegation"):
        errors.append("nested delegation cannot be enabled at depth 2")
    if decision.get("resolved_thinking") == "ultra" and (
        decision.get("execution_level") != "root" or depth != 0
    ):
        errors.append("ultra is root-only")
    if decision.get("execution_level") == "worker" and task_snapshot.get("side_effects") not in {
        "none", "local_reversible"
    }:
        errors.append("worker authority cannot exceed local_reversible side effects")

    route_source = decision.get("route_source")
    if route_source not in {"selected", "inherited"}:
        errors.append("invalid route_source")
    parent_route = decision.get("parent_route")
    if route_source == "inherited":
        if not isinstance(parent_route, dict):
            errors.append("inherited route requires parent_route")
        elif (
            parent_route.get("model") != decision.get("resolved_model")
            or parent_route.get("thinking") != decision.get("resolved_thinking")
            or parent_route.get("capability_snapshot_digest") != digest
        ):
            errors.append("inherited route must exactly match the parent route")
    elif parent_route is not None:
        errors.append("parent_route is only valid for an inherited route")
    if fork_turns == "all" and route_source != "inherited":
        errors.append("full-history forks must inherit the parent route")

    fanout = decision.get("fanout")
    if not isinstance(fanout, dict):
        errors.append("fanout must be an object")
    else:
        expected_fields = {"requested_workers", "independent", "deterministic", "noncolliding"}
        if fanout.keys() != expected_fields:
            errors.append(f"fanout must contain exactly: {sorted(expected_fields)}")
        requested_workers = fanout.get("requested_workers")
        if not isinstance(requested_workers, int) or isinstance(requested_workers, bool) or requested_workers < 0:
            errors.append("fanout.requested_workers must be a non-negative integer")
        elif requested_workers > 10:
            errors.append("fanout cannot exceed 10")
        elif requested_workers > 4 and not all(
            fanout.get(field) is True for field in ("independent", "deterministic", "noncolliding")
        ):
            errors.append("fanout above 4 requires independent, deterministic, noncolliding lanes")
        for field in ("independent", "deterministic", "noncolliding"):
            if not isinstance(fanout.get(field), bool):
                errors.append(f"fanout.{field} must be boolean")

    for field in ("rationale", "quality_gate"):
        if not isinstance(decision.get(field), str) or not decision.get(field):
            errors.append(f"{field} must be a non-empty string")
    if not valid_string_list(decision.get("escalate_when")):
        errors.append("escalate_when must be a non-empty list")
    if decision.get("routing_mode") == "probe_then_escalate":
        escalation = decision.get("escalation_route")
        if not isinstance(escalation, dict):
            errors.append("probe_then_escalate requires escalation_route")
        elif supported_route(capabilities or {}, escalation.get("model"), escalation.get("thinking")) is None:
            errors.append("escalation_route is not supported by the capability snapshot")

    if decision.get("resolved_model") == "gpt-5.6-terra":
        calibration = decision.get("calibration")
        if decision.get("evidence_state") not in {"personal_eval", "runtime_observation"}:
            errors.append("terra requires personalized or runtime evidence")
        if not isinstance(calibration, dict):
            errors.append("terra requires calibration evidence")
        elif calibration.get("runs_per_candidate", 0) < 3 or calibration.get("metric") != "verified_completions_per_minute" or not calibration.get("receipt"):
            errors.append("terra requires a valid calibration receipt")

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
            if field in {"ceiling"}:
                if authority.get(field) not in {"none", "local_reversible", "external_reversible", "irreversible"}:
                    errors.append("authority.ceiling is invalid")
            elif field in {"allowed_actions", "prohibited_actions"}:
                if not valid_string_list(authority.get(field)) or len(set(authority.get(field, []))) != len(authority.get(field, [])):
                    errors.append(f"authority.{field} must be a non-empty unique string list")
            elif not valid_string_list(authority.get(field)):
                errors.append(f"authority.{field} must be a non-empty string list")
        allowed_actions = set(authority.get("allowed_actions", []))
        prohibited_actions = set(authority.get("prohibited_actions", []))
        if decision.get("execution_level") == "worker":
            if authority.get("ceiling") not in {"none", "local_reversible"}:
                errors.append("worker authority ceiling cannot exceed local_reversible")
            if not allowed_actions <= SAFE_WORKER_ACTIONS:
                errors.append("worker authority contains an action above the local-reversible ceiling")
            missing_prohibitions = REQUIRED_WORKER_PROHIBITIONS - prohibited_actions
            if missing_prohibitions:
                errors.append(f"worker authority is missing mandatory prohibitions: {sorted(missing_prohibitions)}")
    return errors


def main() -> None:
    example_dir = ROOT / "examples/routing"
    capabilities = json.loads((example_dir / "capability-snapshot.json").read_text(encoding="utf-8"))
    for path in sorted(example_dir.glob("valid-*.json")):
        errors = validate(json.loads(path.read_text(encoding="utf-8")), capabilities, allow_test_fixture=True)
        if errors:
            raise SystemExit(f"{path.name} should be valid: {errors}")
    for path in sorted(example_dir.glob("invalid-*.json")):
        if not validate(json.loads(path.read_text(encoding="utf-8")), capabilities, allow_test_fixture=True):
            raise SystemExit(f"{path.name} unexpectedly passed")
    cases = json.loads((example_dir / "routing-cases.json").read_text(encoding="utf-8"))
    for case in cases:
        if supported_route(capabilities, case.get("model"), case.get("thinking")) is None:
            raise SystemExit(f"routing case is not supported by capability snapshot: {case!r}")
    print("CAPS dynamic routing verification passed.")


if __name__ == "__main__":
    main()
