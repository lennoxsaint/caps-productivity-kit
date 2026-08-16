#!/usr/bin/env python3
"""Evaluate recent CAPS receipts and emit conservative route recommendations."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


FAMILIES = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")


def load_receipts(path: Path, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    receipts = []
    if not path.exists():
        return receipts
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if datetime.fromisoformat(item["finished_at"]) >= cutoff:
                receipts.append(item)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"invalid receipt at {path}:{line_number}: {error}") from error
    return receipts


def exclusion_reason(item: dict) -> str | None:
    """Return why a receipt cannot influence routing, or None when it can."""
    if item.get("schema_version") != "1.2":
        return "legacy_capability_unverified"
    if item.get("lifecycle_state") != "completed":
        return "lifecycle_incomplete"
    if item.get("binding_state") != "bound":
        return "worker_unbound"
    if not item.get("capability_verified"):
        return "capability_not_verified"
    if item.get("observability_state") != "complete":
        return "observability_degraded"
    if not item.get("task_snapshot_complete"):
        return "task_snapshot_incomplete"
    # Derive qualification from the auditable lifecycle fields instead of the
    # cached learning label. Early 1.2 writers marked failed or partially
    # delegated work ineligible, which would create survivorship bias. Quality
    # failures, severe errors, retries, and rework are scored below.
    return None


def resolved_route(item: dict) -> tuple[str, str]:
    return (
        item.get("resolved_model", item.get("model")),
        item.get("resolved_thinking", item.get("thinking")),
    )


def score(items: list[dict]) -> dict:
    work_seconds = sum(float(item["elapsed_seconds"]) for item in items)
    rework_seconds = sum(float(item.get("rework_seconds", 0)) for item in items)
    elapsed = work_seconds + rework_seconds
    passes = sum(bool(item["quality_passed"]) and not item["severe_error"] for item in items)
    failures = len(items) - passes
    return {
        "receipts": len(items),
        "passes": passes,
        "failures": failures,
        "pass_rate": round(passes / len(items), 4) if items else 0,
        "severe_errors": sum(bool(item["severe_error"]) for item in items),
        "incomplete_snapshots": sum(not bool(item.get("task_snapshot_complete")) for item in items),
        "weak_delegations": sum(item.get("delegation_quality") != "complete" for item in items),
        "rework_seconds": round(rework_seconds, 3),
        "elapsed_seconds": round(elapsed, 3),
        "verified_completions_per_minute": round(passes * 60 / max(elapsed, 0.001), 4),
    }


def evaluate(receipts: list[dict], min_total: int, min_candidate: int, margin: float) -> dict:
    grouped: dict[str, dict[tuple[str, str], list[dict]]] = defaultdict(lambda: defaultdict(list))
    observed_classes: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()
    for item in receipts:
        task_class = item.get("task_class", "unknown")
        observed_classes[task_class] += 1
        reason = exclusion_reason(item)
        if reason:
            exclusion_reasons[reason] += 1
            continue
        model, thinking = resolved_route(item)
        grouped[task_class][(model, thinking)].append(item)

    classes = {}
    for task_class in sorted(observed_classes):
        candidates = grouped[task_class]
        scored = {
            f"{model}/{thinking}": {"model": model, "thinking": thinking, **score(items)}
            for (model, thinking), items in sorted(candidates.items())
        }
        families = {value["model"] for value in scored.values() if value["receipts"] >= min_candidate}
        eligible = [
            value for value in scored.values()
            if value["receipts"] >= min_candidate
            and value["pass_rate"] == 1.0
            and value["severe_errors"] == 0
            and value["incomplete_snapshots"] == 0
            and value["weak_delegations"] == 0
        ]
        eligible.sort(key=lambda value: value["verified_completions_per_minute"], reverse=True)
        total = sum(value["receipts"] for value in scored.values())
        winner = eligible[0] if eligible else None
        runner_up = eligible[1] if len(eligible) > 1 else None
        gain = None
        if winner and runner_up:
            baseline = runner_up["verified_completions_per_minute"]
            gain = (winner["verified_completions_per_minute"] - baseline) / max(baseline, 0.0001)
        blockers = []
        if total < min_total:
            blockers.append(f"need_{min_total - total}_more_receipts")
        if set(FAMILIES) - families:
            blockers.append("missing_balanced_luna_terra_sol_samples")
        if winner is None or runner_up is None:
            blockers.append("fewer_than_two_passing_candidates")
        elif gain is None or gain < margin:
            blockers.append("material_margin_not_met")
        promoted = not blockers
        classes[task_class] = {
            "observed_receipts": observed_classes[task_class],
            "total_receipts": total,
            "excluded_receipts": observed_classes[task_class] - total,
            "candidates": scored,
            "recommendation": {
                "promoted": promoted,
                "model": winner["model"] if promoted else None,
                "thinking": winner["thinking"] if promoted else None,
                "material_gain": round(gain, 4) if gain is not None else None,
                "blockers": blockers,
            },
        }

    qualified_count = sum(sum(len(items) for items in candidates.values()) for candidates in grouped.values())
    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "receipt_count": len(receipts),
        "qualified_receipt_count": qualified_count,
        "excluded_receipt_count": len(receipts) - qualified_count,
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "window_days": 30,
        "minimum_total_per_class": min_total,
        "minimum_per_candidate": min_candidate,
        "material_margin": margin,
        "task_classes": classes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path.home() / ".codex/routing/receipts.jsonl")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--minimum-total", type=int, default=30)
    parser.add_argument("--minimum-per-candidate", type=int, default=5)
    parser.add_argument("--material-margin", type=float, default=0.10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(
        load_receipts(args.store.expanduser(), args.days),
        args.minimum_total,
        args.minimum_per_candidate,
        args.material_margin,
    )
    result["window_days"] = args.days
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
