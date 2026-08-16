#!/usr/bin/env python3
"""Build and verify a runtime model capability snapshot.

The snapshot is deliberately supplied by the runtime. CAPS does not infer model
availability from a model name and does not maintain a baked-in model catalog.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


DIGEST_PREFIX = "sha256:"
REQUIRED_MODEL_FIELDS = {
    "id",
    "provider",
    "reasoning_levels",
    "live",
    "entitled",
    "allowed_by_policy",
    "specialist_task_classes",
}
REQUIRED_SNAPSHOT_FIELDS = {"snapshot_version", "captured_at", "source", "models"}
RUNTIME_SOURCE = "codex-runtime-model-catalog"
FIXTURE_SOURCE = "caps-test-fixture"
ALLOWED_SOURCES = {RUNTIME_SOURCE, FIXTURE_SOURCE}


def canonical_payload(snapshot: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in snapshot.items() if key != "digest"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    return DIGEST_PREFIX + hashlib.sha256(canonical_payload(snapshot)).hexdigest()


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["capability catalog must be an object"]
    missing = REQUIRED_SNAPSHOT_FIELDS - catalog.keys()
    if missing:
        errors.append(f"missing capability snapshot fields: {sorted(missing)}")
    unknown = catalog.keys() - REQUIRED_SNAPSHOT_FIELDS - {"digest"}
    if unknown:
        errors.append(f"unknown capability snapshot fields: {sorted(unknown)}")
    for field in ("snapshot_version", "captured_at", "source"):
        if not isinstance(catalog.get(field), str) or not catalog.get(field):
            errors.append(f"{field} must be a non-empty string")
    if catalog.get("source") not in ALLOWED_SOURCES:
        errors.append(f"source must be one of: {sorted(ALLOWED_SOURCES)}")
    captured_at = catalog.get("captured_at")
    if isinstance(captured_at, str) and captured_at:
        try:
            parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            errors.append("captured_at must be an RFC 3339 timestamp with timezone")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, model in enumerate(models):
        label = f"models[{index}]"
        if not isinstance(model, dict):
            errors.append(f"{label} must be an object")
            continue
        missing_model = REQUIRED_MODEL_FIELDS - model.keys()
        if missing_model:
            errors.append(f"{label} missing fields: {sorted(missing_model)}")
        unknown_model = model.keys() - REQUIRED_MODEL_FIELDS
        if unknown_model:
            errors.append(f"{label} has unknown fields: {sorted(unknown_model)}")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            errors.append(f"{label}.id must be a non-empty string")
        elif model_id in seen:
            errors.append(f"duplicate model id: {model_id}")
        else:
            seen.add(model_id)
        if not isinstance(model.get("provider"), str) or not model.get("provider"):
            errors.append(f"{label}.provider must be a non-empty string")
        levels = model.get("reasoning_levels")
        if not isinstance(levels, list) or not levels or not all(isinstance(item, str) and item for item in levels):
            errors.append(f"{label}.reasoning_levels must be a non-empty string list")
        elif len(set(levels)) != len(levels):
            errors.append(f"{label}.reasoning_levels must be unique")
        specialists = model.get("specialist_task_classes")
        if not isinstance(specialists, list) or not all(isinstance(item, str) and item for item in specialists):
            errors.append(f"{label}.specialist_task_classes must be a string list")
        for field in ("live", "entitled", "allowed_by_policy"):
            if not isinstance(model.get(field), bool):
                errors.append(f"{label}.{field} must be boolean")
    digest = catalog.get("digest")
    if digest is not None and digest != snapshot_digest(catalog):
        errors.append("capability snapshot digest is invalid")
    return errors


def build_snapshot(catalog: dict[str, Any]) -> dict[str, Any]:
    snapshot = {key: value for key, value in catalog.items() if key != "digest"}
    errors = validate_catalog(snapshot)
    if errors:
        raise ValueError("; ".join(errors))
    snapshot["digest"] = snapshot_digest(snapshot)
    return snapshot


def validate_runtime_provenance(snapshot: dict[str, Any], *, max_age_seconds: int, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    if snapshot.get("source") != RUNTIME_SOURCE:
        errors.append(f"live routing requires source={RUNTIME_SOURCE}")
        return errors
    try:
        captured_at = datetime.fromisoformat(str(snapshot.get("captured_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return ["captured_at must be an RFC 3339 timestamp with timezone"]
    if captured_at.tzinfo is None:
        return ["captured_at must be an RFC 3339 timestamp with timezone"]
    current = now or datetime.now(timezone.utc)
    age = (current - captured_at.astimezone(timezone.utc)).total_seconds()
    if age < -30:
        errors.append("runtime capability snapshot is from the future")
    elif age > max_age_seconds:
        errors.append("runtime capability snapshot is stale")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path, help="Runtime capability catalog JSON")
    parser.add_argument("--output", type=Path, help="Write the signed snapshot to this path")
    parser.add_argument("--max-age-seconds", type=int, default=300, help="Maximum age for live runtime readback")
    parser.add_argument("--allow-test-fixture", action="store_true", help="Allow the explicit caps-test-fixture source for repository tests")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    snapshot = build_snapshot(catalog)
    if not args.allow_test_fixture or snapshot.get("source") != FIXTURE_SOURCE:
        provenance_errors = validate_runtime_provenance(snapshot, max_age_seconds=args.max_age_seconds)
        if provenance_errors:
            raise SystemExit("; ".join(provenance_errors))
    rendered = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
