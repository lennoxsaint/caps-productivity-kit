#!/usr/bin/env python3
"""Evaluate recent CAPS receipts and emit conservative route recommendations."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


FAMILIES = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")


def load_receipts(path: Path, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    receipts = []
    if not path.exists():
        return receipts
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if datetime.fromisoformat(item["finished_at"]) >= cutoff:
                receipts.append(item)
        except (json.JSONDecodeError, KeyError, ValueError) as error:
            raise SystemExit(f"invalid receipt at {path}:{line_number}: {error}") from error
    return receipts


def score(items: list[dict]) -> dict:
    elapsed = sum(float(item["elapsed_seconds"]) + float(item.get("rework_seconds", 0)) for item in items)
    passes = sum(bool(item["quality_passed"]) and not item["severe_error"] for item in items)
    return {
        "receipts": len(items),
        "passes": passes,
        "pass_rate": round(passes / len(items), 4) if items else 0,
        "severe_errors": sum(bool(item["severe_error"]) for item in items),
        "incomplete_snapshots": sum(not bool(item.get("task_snapshot_complete")) for item in items),
        "weak_delegations": sum(item.get("delegation_quality") != "complete" for item in items),
        "elapsed_seconds": round(elapsed, 3),
        "verified_completions_per_minute": round(passes * 60 / max(elapsed, 0.001), 4),
    }


def evaluate(receipts: list[dict], min_total: int, min_candidate: int, margin: float) -> dict:
    grouped: dict[str, dict[tuple[str, str], list[dict]]] = defaultdict(lambda: defaultdict(list))
    for item in receipts:
        grouped[item["task_class"]][(item["model"], item["thinking"])].append(item)
    classes = {}
    for task_class, candidates in sorted(grouped.items()):
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
            "total_receipts": total,
            "candidates": scored,
            "recommendation": {
                "promoted": promoted,
                "model": winner["model"] if promoted else None,
                "thinking": winner["thinking"] if promoted else None,
                "material_gain": round(gain, 4) if gain is not None else None,
                "blockers": blockers,
            },
        }
    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "receipt_count": len(receipts),
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
    result = evaluate(load_receipts(args.store.expanduser(), args.days), args.minimum_total, args.minimum_per_candidate, args.material_margin)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
