#!/usr/bin/env python3
"""Evaluate one supplied CAPS model bakeoff without invoking any model."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
PRICE_ORDER = {model: index for index, model in enumerate(MODELS)}
PERFORMANCE_MARGIN = 0.10
PROVISIONAL_TTL_DAYS = 30

TASKS = (
    {
        "task_id": "deterministic-transformation-v1",
        "task_class": "transformation",
        "public_safe": True,
        "objective": "Normalize the supplied public book records into canonical JSON.",
        "input": [
            {"title": "  Delta ", "tags": ["two", "one", "two"]},
            {"title": "Alpha", "tags": []},
        ],
        "required_output": [
            {"title": "Alpha", "tags": []},
            {"title": "Delta", "tags": ["one", "two"]},
        ],
        "instructions": [
            "Trim titles, de-duplicate and sort tags, then sort records by title.",
            "Return only valid JSON and do not alter the supplied source record.",
        ],
        "mandatory_gates": ["exact_output", "schema_valid", "source_unchanged"],
    },
    {
        "task_id": "bounded-coding-v1",
        "task_class": "coding",
        "public_safe": True,
        "objective": "Implement clamp(value, lower, upper) in one dependency-free Python module.",
        "input": {
            "starter": "def clamp(value, lower, upper):\n    raise NotImplementedError\n",
            "cases": [[5, 0, 10, 5], [-1, 0, 10, 0], [11, 0, 10, 10]],
        },
        "required_output": "A direct implementation that rejects lower greater than upper with ValueError.",
        "instructions": [
            "Change only the supplied function body.",
            "Run the three supplied cases and one reversed-bound regression case.",
        ],
        "mandatory_gates": ["targeted_tests_passed", "project_checks_passed", "scope_preserved"],
    },
    {
        "task_id": "proof-state-review-v1",
        "task_class": "proof_review",
        "public_safe": True,
        "objective": "Classify delivery claims without upgrading the supplied proof state.",
        "input": [
            {"claim": "The release is deployed.", "evidence": "A local build passed."},
            {"claim": "The message was read.", "evidence": "The provider returned a sent receipt."},
            {"claim": "The draft is ready for review.", "evidence": "The draft file exists and opens."},
        ],
        "required_output": ["unsupported", "unsupported", "supported"],
        "instructions": [
            "Use only the supplied evidence.",
            "Distinguish local, sent, delivered, read, deployed, and approved states exactly.",
        ],
        "mandatory_gates": ["claims_supported", "proof_states_exact", "no_unauthorized_claims"],
    },
)

PUBLIC_FALLBACK = {
    "transformation": {"model": "gpt-5.6-luna", "thinking": "low"},
    "coding": {"model": "gpt-5.6-sol", "thinking": "medium"},
    "proof_review": {"model": "gpt-5.6-sol", "thinking": "high"},
}

THINKING_BY_TASK_AND_MODEL = {
    "transformation": {"gpt-5.6-luna": "low", "gpt-5.6-terra": "high", "gpt-5.6-sol": "medium"},
    "coding": {"gpt-5.6-luna": "high", "gpt-5.6-terra": "high", "gpt-5.6-sol": "medium"},
    "proof_review": {"gpt-5.6-luna": "high", "gpt-5.6-terra": "high", "gpt-5.6-sol": "high"},
}

SHA256_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def task_manifest() -> dict:
    tasks = copy.deepcopy(list(TASKS))
    return {
        "bakeoff_version": "0.4.0",
        "execution_mode": "manual_external_runs_only",
        "tasks_digest": hashlib.sha256(_canonical_json(tasks).encode()).hexdigest(),
        "tasks": tasks,
    }


def _parse_evaluated_at(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("evaluated_at must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("evaluated_at must be a timezone-aware ISO-8601 string") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("evaluated_at must be a timezone-aware ISO-8601 string")
    return parsed.astimezone(timezone.utc)


def _validate_record(
    record: object,
    task_by_id: dict[str, dict],
    frozen_tasks_digest: str,
    index: int,
) -> tuple[str, str]:
    label = f"results[{index}]"
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be an object")
    task_id = record.get("task_id")
    model = record.get("model")
    if task_id not in task_by_id:
        raise ValueError(f"{label}.task_id is unknown")
    if model not in MODELS:
        raise ValueError(f"{label}.model is unknown")
    if record.get("tasks_digest") != frozen_tasks_digest:
        raise ValueError(f"{label}.tasks_digest must match the frozen task manifest")
    capability_digest = record.get("capability_snapshot_digest")
    if not isinstance(capability_digest, str) or not SHA256_DIGEST_PATTERN.fullmatch(
        capability_digest
    ):
        raise ValueError(
            f"{label}.capability_snapshot_digest must be sha256:<64 lowercase hex characters>"
        )
    receipt_ref_hash = record.get("receipt_ref_hash")
    if not isinstance(receipt_ref_hash, str) or not SHA256_DIGEST_PATTERN.fullmatch(
        receipt_ref_hash
    ):
        raise ValueError(f"{label}.receipt_ref_hash must be sha256:<64 lowercase hex characters>")
    for field in ("capability_available", "isolated", "read_only", "completed", "severe_error"):
        if not isinstance(record.get(field), bool):
            raise ValueError(f"{label}.{field} must be a boolean")
    if not record["isolated"]:
        raise ValueError(f"{label}.isolated must be true")
    if not record["read_only"]:
        raise ValueError(f"{label}.read_only must be true")
    if not isinstance(record.get("capability_source"), str) or not record["capability_source"].strip():
        raise ValueError(f"{label}.capability_source must be a non-empty string")
    elapsed = record.get("elapsed_seconds")
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed <= 0:
        raise ValueError(f"{label}.elapsed_seconds must be greater than zero")
    if not record["capability_available"] and record["completed"]:
        raise ValueError(f"{label} cannot be completed when capability_available is false")
    gates = record.get("gates")
    expected_gates = set(task_by_id[task_id]["mandatory_gates"])
    if not isinstance(gates, dict) or set(gates) != expected_gates:
        raise ValueError(f"{label}.gates must exactly match {sorted(expected_gates)}")
    if not all(isinstance(value, bool) for value in gates.values()):
        raise ValueError(f"{label}.gates values must be booleans")
    return task_id, model


def _score(record: dict) -> dict:
    supported = record["capability_available"]
    correctness_passed = (
        supported
        and record["completed"]
        and not record["severe_error"]
        and all(record["gates"].values())
    )
    return {
        "model": record["model"],
        "capability_available": supported,
        "mandatory_correctness_passed": correctness_passed,
        "elapsed_seconds": float(record["elapsed_seconds"]),
        "verified_completions_per_minute": round(60 / float(record["elapsed_seconds"]), 4)
        if correctness_passed
        else 0.0,
    }


def _verified_rate(candidate: dict) -> float:
    if not candidate["mandatory_correctness_passed"]:
        return 0.0
    return 60 / candidate["elapsed_seconds"]


def _recommend(task: dict, records: list[dict]) -> dict:
    candidates = [_score(record) for record in records]
    passing = [candidate for candidate in candidates if candidate["mandatory_correctness_passed"]]
    fastest = sorted(
        passing,
        key=lambda candidate: (-_verified_rate(candidate), PRICE_ORDER[candidate["model"]]),
    )
    selection_basis = "no_passing_private_route"
    selected = None
    performance_lead = None
    if len(fastest) >= 2:
        winner, runner_up = fastest[:2]
        baseline = _verified_rate(runner_up)
        performance_lead = (_verified_rate(winner) - baseline) / baseline
        if performance_lead >= PERFORMANCE_MARGIN:
            selected = winner
            selection_basis = "performance_lead"
    if selected is None and passing:
        selected = min(passing, key=lambda candidate: PRICE_ORDER[candidate["model"]])
        selection_basis = "least_expensive_passing"
    return {
        "task_id": task["task_id"],
        "task_class": task["task_class"],
        "model": selected["model"] if selected else None,
        "thinking": THINKING_BY_TASK_AND_MODEL[task["task_class"]][selected["model"]]
        if selected
        else None,
        "selection_basis": selection_basis,
        "performance_lead": round(performance_lead, 4) if performance_lead is not None else None,
        "minimum_performance_lead": PERFORMANCE_MARGIN,
        "metric": "verified_completions_per_minute",
        "excluded_unsupported_models": sorted(
            candidate["model"] for candidate in candidates if not candidate["capability_available"]
        ),
        "excluded_failed_models": sorted(
            candidate["model"]
            for candidate in candidates
            if candidate["capability_available"] and not candidate["mandatory_correctness_passed"]
        ),
        "candidates": sorted(candidates, key=lambda candidate: PRICE_ORDER[candidate["model"]]),
    }


def evaluate(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("results payload must be an object")
    if payload.get("schema_version") != "1.0":
        raise ValueError("schema_version must be 1.0")
    evaluated_at = _parse_evaluated_at(payload.get("evaluated_at"))
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(TASKS) * len(MODELS):
        raise ValueError("results must contain exactly 9 records")
    manifest = task_manifest()
    task_by_id = {task["task_id"]: task for task in TASKS}
    pairs = [
        _validate_record(record, task_by_id, manifest["tasks_digest"], index)
        for index, record in enumerate(results)
    ]
    expected_pairs = {(task["task_id"], model) for task in TASKS for model in MODELS}
    if set(pairs) != expected_pairs or len(set(pairs)) != len(pairs):
        raise ValueError("results must contain exactly one result for every task/model pair")
    capability_digests = {record["capability_snapshot_digest"] for record in results}
    if len(capability_digests) != 1:
        raise ValueError("results must bind to the same capability_snapshot_digest")
    receipt_ref_hashes = [record["receipt_ref_hash"] for record in results]
    if len(set(receipt_ref_hashes)) != len(receipt_ref_hashes):
        raise ValueError("results must bind to a unique receipt_ref_hash")

    recommendations = []
    for task in TASKS:
        task_records = [record for record in results if record["task_id"] == task["task_id"]]
        recommendations.append(_recommend(task, task_records))
    valid_until = evaluated_at + timedelta(days=PROVISIONAL_TTL_DAYS)
    result_by_pair = {(record["task_id"], record["model"]): record for record in results}
    result_bindings = [
        {
            "task_id": task["task_id"],
            "model": model,
            "receipt_ref_hash": result_by_pair[(task["task_id"], model)]["receipt_ref_hash"],
        }
        for task in TASKS
        for model in MODELS
    ]
    return {
        "schema_version": "1.0",
        "bakeoff_version": "0.4.0",
        "execution_mode": "evaluate_supplied_results_only",
        "tasks_digest": manifest["tasks_digest"],
        "traceability": {
            "tasks_digest": manifest["tasks_digest"],
            "capability_snapshot_digest": next(iter(capability_digests)),
            "result_bindings": result_bindings,
        },
        "profile": {
            "profile_version": "caps-0.4.0-model-bakeoff-provisional",
            "visibility": "private",
            "evidence_state": "one_time_personal_eval",
            "provisional": True,
            "valid_from": evaluated_at.isoformat(),
            "valid_until": valid_until.isoformat(),
            "ttl_days": PROVISIONAL_TTL_DAYS,
            "recommendations": recommendations,
        },
        "public_fallback": PUBLIC_FALLBACK,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--results", type=Path, help="JSON file containing exactly nine supplied result records")
    group.add_argument("--print-tasks", action="store_true", help="Print the frozen public-safe task manifest")
    args = parser.parse_args()
    try:
        output = task_manifest() if args.print_tasks else evaluate(json.loads(args.results.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
