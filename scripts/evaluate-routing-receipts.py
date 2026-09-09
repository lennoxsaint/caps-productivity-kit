#!/usr/bin/env python3
"""Evaluate redacted CAPS receipts and emit conservative recommendations.

The evaluator is intentionally recommendation-only.  It reads the one
append-only receipt stream, applies linked owner-correction events in memory,
and never edits a saved route or rewrites a historical receipt.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


RECEIPT_EVENT = "receipt"
CORRECTION_EVENT = "correction"
CURRENT_SCHEMA = "1.2"


def event_type(item: dict) -> str:
    # Rows written before typed events existed are receipts by definition.
    return item.get("event_type", RECEIPT_EVENT)


def event_timestamp(item: dict) -> str:
    field = "corrected_at" if event_type(item) == CORRECTION_EVENT else "finished_at"
    value = item.get(field)
    if not isinstance(value, str):
        raise ValueError(f"missing {field}")
    return value


def load_entries(path: Path, days: int) -> list[dict]:
    """Load recent receipt and correction events without normalizing unknowns."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    parsed_rows: list[tuple[dict, datetime]] = []
    if not path.exists():
        return []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise TypeError("receipt row must be an object")
            timestamp = datetime.fromisoformat(event_timestamp(item))
            if timestamp.tzinfo is None:
                raise ValueError("timestamp must include a timezone")
            parsed_rows.append((item, timestamp.astimezone(timezone.utc)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise SystemExit(f"invalid receipt at {path}:{line_number}: {error}") from error
    # A correction can be the only evidence generated this week for an older
    # accepted receipt.  Keep that linked base row in the read-only window so
    # its rework is not silently dropped from the digest.
    recent_correction_ids = {
        item.get("receipt_id")
        for item, timestamp in parsed_rows
        if event_type(item) == CORRECTION_EVENT and timestamp >= cutoff
    }
    return [
        item for item, timestamp in parsed_rows
        if timestamp >= cutoff
        or (event_type(item) != CORRECTION_EVENT and item.get("receipt_id") in recent_correction_ids)
    ]


def load_receipts(path: Path, days: int) -> list[dict]:
    """Compatibility helper returning only base receipt rows."""
    return [item for item in load_entries(path, days) if event_type(item) != CORRECTION_EVENT]


def correction_map(entries: Iterable[dict]) -> dict[str, list[dict]]:
    """Group correction events and ignore a repeated event identity once."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for item in entries:
        if event_type(item) != CORRECTION_EVENT:
            continue
        receipt_id = item.get(
            "receipt_id",
            item.get("corrects_receipt_id", item.get("correction_of_receipt_id")),
        )
        if not isinstance(receipt_id, str):
            continue
        identity = str(item.get("correction_id") or item.get("idempotency_key_hash") or id(item))
        key = (receipt_id, identity)
        if key in seen:
            continue
        seen.add(key)
        grouped[receipt_id].append(item)
    return grouped


def exclusion_reason(item: dict) -> str | None:
    """Return why a receipt cannot influence routing, or None when it can."""
    if event_type(item) == CORRECTION_EVENT:
        return "correction_event"
    if item.get("schema_version") != CURRENT_SCHEMA:
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
    # Do not use the cached learning label.  Complete failures and rework are
    # calibration evidence, while a degraded label must not create survivorship
    # bias.
    return None


def resolved_route(item: dict) -> tuple[str | None, str | None]:
    return (
        item.get("resolved_model", item.get("model")),
        item.get("resolved_thinking", item.get("thinking")),
    )


def lead_review_status(item: dict) -> str:
    """Return pass/fail/unknown without turning a legacy omission into pass."""
    if "lead_reviewed" in item:
        value = item.get("lead_reviewed")
        if value is True or (isinstance(value, str) and value.lower() in {"pass", "passed", "true"}):
            return "pass"
        if value is False or (isinstance(value, str) and value.lower() in {"fail", "failed", "false"}):
            return "fail"
        return "unknown"
    # Accept a descriptive alias in hand-authored private profiles, while the
    # public writer stores the boolean marker above.
    if "lead_review" in item:
        value = item.get("lead_review")
        if isinstance(value, dict):
            value = value.get("passed", value.get("reviewed"))
        if value is True or (isinstance(value, str) and value.lower() in {"pass", "passed", "true"}):
            return "pass"
        if value is False or (isinstance(value, str) and value.lower() in {"fail", "failed", "false"}):
            return "fail"
        return "unknown"
    return "legacy"


def _check_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict) and isinstance(value.get("passed"), bool):
        return value["passed"]
    return None


def task_checks_status(item: dict) -> str:
    """Return the independently recorded task-check state."""
    explicit: bool | None = None
    explicit_present = False
    for field in ("task_checks_passed", "checks_passed", "acceptance_checks_passed"):
        if field in item:
            explicit_present = True
            explicit = _check_value(item.get(field))
            break

    checks = item.get("task_checks", item.get("acceptance_checks", item.get("checks")))
    if isinstance(checks, dict):
        values = [_check_value(value) for value in checks.values()]
    elif isinstance(checks, list):
        values = [_check_value(value) for value in checks]
    else:
        values = []
    if explicit_present:
        # A summary marker may be supplied without named checks for old or
        # hand-authored rows.  When detail is present, however, it must agree
        # with the detail; contradictory evidence is never accepted.
        if explicit is False:
            return "fail"
        if explicit is None:
            return "unknown"
        if not values:
            return "pass"
        if any(value is False for value in values):
            return "fail"
        if all(value is True for value in values):
            return "pass"
        return "unknown"
    if not values:
        return "legacy" if not any(field in item for field in ("task_checks", "acceptance_checks", "checks")) else "unknown"
    if any(value is False for value in values):
        return "fail"
    if all(value is True for value in values):
        return "pass"
    return "unknown"


def acceptance_state(item: dict) -> str:
    """Calculate accepted/rejected/unknown from checks and independent review."""
    if item.get("lifecycle_state") != "completed":
        return "rejected"
    basic_pass = (
        item.get("quality_passed") is True
        and item.get("outcome") == "pass"
        and item.get("gate_result", "pass") == "pass"
        and not item.get("severe_error", False)
    )
    if not basic_pass:
        return "rejected"
    review = lead_review_status(item)
    checks = task_checks_status(item)
    # Legacy rows predate the independent acceptance fields.  Keep them
    # readable and unchanged, but never turn an omitted review/check marker
    # into a new verified successful outcome.
    if review == "legacy" or checks == "legacy":
        return "unknown"
    if review == "pass" and checks == "pass":
        return "accepted"
    if review == "fail" or checks == "fail":
        return "rejected"
    return "unknown"


def _number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _usage_value(item: dict) -> float | None:
    """Read only explicit measured-usage fields; tokens/cost are excluded."""
    for field in (
        "subscription_usage", "available_usage", "available_subscription_usage",
        "available_subscription_units", "subscription_units", "usage_units", "usage",
    ):
        if field in item:
            return _number(item.get(field))
    return None


def effective_item(item: dict, corrections: Iterable[dict] = ()) -> dict:
    """Apply corrections to a copy for scoring; never rewrite the source row."""
    result = dict(item)
    events = list(corrections)
    # The base writer stores zero, but tolerate old rows that omitted the
    # additive fields.  Missing subscription usage intentionally remains None.
    base_rework = _number(result.get("rework_seconds"))
    result["rework_seconds"] = base_rework if base_rework is not None else 0.0
    base_attempts = result.get("attempts")
    if not isinstance(base_attempts, int) or isinstance(base_attempts, bool) or base_attempts < 1:
        retry_count = result.get("retry_count", 0)
        base_attempts = retry_count + 1 if isinstance(retry_count, int) and retry_count >= 0 else 1
    result["attempts"] = base_attempts
    result["correction_count"] = len(events)
    result["owner_correction_count"] = sum(bool(event.get("owner_correction", True)) for event in events)

    usage_values: list[float] = []
    base_usage = _usage_value(result)
    usage_known = base_usage is not None
    if usage_known:
        usage_values.append(float(base_usage))
    for event in events:
        rework = _number(event.get("rework_seconds"))
        if rework is not None:
            result["rework_seconds"] += rework
        attempts_added = event.get("attempts_added", 1)
        if isinstance(attempts_added, int) and not isinstance(attempts_added, bool) and attempts_added >= 0:
            result["attempts"] += attempts_added
        usage = _usage_value(event)
        if usage is None:
            usage_known = False
        else:
            usage_values.append(float(usage))
        accepted_after = event.get("accepted_after", event.get("accepted"))
        if accepted_after is False or event.get("correction_outcome") == "fail":
            # This is derived state only.  The original accepted receipt stays
            # byte-for-byte intact in the append-only stream.
            result["quality_passed"] = False
            result["outcome"] = "fail"
            result["gate_result"] = "fail"
            result["_correction_rejected"] = True
    result["_subscription_usage_total"] = round(sum(usage_values), 6) if usage_known else None
    return result


def score(items: list[dict]) -> dict:
    items = [
        effective_item(item) if "_subscription_usage_total" not in item else item
        for item in items
    ]
    work_values = [_number(item.get("elapsed_seconds")) for item in items]
    work_unknown = sum(value is None for value in work_values)
    work_seconds = sum(value for value in work_values if value is not None)
    rework_seconds = sum(float(item.get("rework_seconds", 0.0)) for item in items)
    elapsed = work_seconds + rework_seconds
    states = [acceptance_state(item) for item in items]
    passes = sum(state == "accepted" for state in states)
    failures = sum(state == "rejected" for state in states)
    usage_values = [item.get("_subscription_usage_total") for item in items]
    usage_unknown = sum(value is None for value in usage_values)
    usage_total = (
        None
        if not items or usage_unknown
        else round(sum(float(value) for value in usage_values), 6)
    )
    accepted_per_usage = (
        round(passes / usage_total, 6)
        if usage_total is not None and usage_total > 0
        else None
    )
    elapsed_metric = round(passes * 60 / max(elapsed, 0.001), 4) if not work_unknown and elapsed > 0 else None
    return {
        "receipts": len(items),
        "passes": passes,
        "accepted_outcomes": passes,
        "failures": failures,
        "unknown_acceptance": sum(state == "unknown" for state in states),
        "pass_rate": round(passes / len(items), 4) if items else 0,
        "severe_errors": sum(bool(item.get("severe_error")) for item in items),
        "incomplete_snapshots": sum(not bool(item.get("task_snapshot_complete")) for item in items),
        "weak_delegations": sum(item.get("delegation_quality") != "complete" for item in items),
        # A missing marker on a legacy row is reported separately.  It remains
        # unknown evidence, but retaining the old recommendation behavior is
        # part of receipt compatibility.
        "lead_review_unknown": sum(lead_review_status(item) == "unknown" for item in items),
        "lead_review_legacy": sum(lead_review_status(item) == "legacy" for item in items),
        "lead_review_failures": sum(lead_review_status(item) == "fail" for item in items),
        "failed_checks": sum(task_checks_status(item) == "fail" for item in items),
        "task_checks_unknown": sum(task_checks_status(item) == "unknown" for item in items),
        "task_checks_legacy": sum(task_checks_status(item) == "legacy" for item in items),
        "legacy_receipts": sum(
            lead_review_status(item) == "legacy" and task_checks_status(item) == "legacy"
            for item in items
        ),
        "corrected_receipts": sum(bool(item.get("_correction_rejected")) for item in items),
        "correction_events": sum(int(item.get("correction_count", 0)) for item in items),
        "owner_correction_events": sum(int(item.get("owner_correction_count", 0)) for item in items),
        "attempts": sum(int(item.get("attempts", 1)) for item in items),
        "rework_seconds": round(rework_seconds, 3),
        "elapsed_seconds": round(elapsed, 3),
        "elapsed_unknown": work_unknown,
        "subscription_usage_total": usage_total,
        "subscription_usage_observed_receipts": len(items) - usage_unknown,
        "subscription_usage_unknown_receipts": usage_unknown,
        "accepted_outcomes_per_subscription_usage": accepted_per_usage,
        # Retain the historical observational metric for old evaluations and
        # as a fallback when subscription units were not measured.
        "verified_completions_per_minute": elapsed_metric,
    }


def _base_receipts(entries: Iterable[dict]) -> list[dict]:
    return [item for item in entries if event_type(item) != CORRECTION_EVENT]


def evaluate(receipts: list[dict], min_total: int, min_candidate: int, margin: float) -> dict:
    entries = list(receipts)
    bases = _base_receipts(entries)
    corrections = correction_map(entries)
    grouped: dict[str, dict[tuple[str | None, str | None], list[dict]]] = defaultdict(lambda: defaultdict(list))
    observed_classes: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()
    for item in bases:
        task_class = item.get("task_class", "unknown")
        observed_classes[task_class] += 1
        reason = exclusion_reason(item)
        if reason:
            exclusion_reasons[reason] += 1
            continue
        model, thinking = resolved_route(item)
        grouped[task_class][(model, thinking)].append(
            effective_item(item, corrections.get(item.get("receipt_id"), []))
        )

    classes = {}
    for task_class in sorted(observed_classes):
        candidates = grouped[task_class]
        scored = {
            f"{model}/{thinking}": {
                "model": model,
                "thinking": thinking,
                **score(items),
            }
            for (model, thinking), items in sorted(candidates.items(), key=lambda pair: str(pair[0]))
        }
        comparable_candidates = [
            value for value in scored.values() if value["receipts"] >= min_candidate
        ]
        usage_comparable = bool(comparable_candidates) and all(
            value["subscription_usage_total"] is not None for value in comparable_candidates
        )
        comparison_metric = (
            "accepted_outcomes_per_subscription_usage"
            if usage_comparable
            else "verified_completions_per_minute"
        )
        eligible = [
            value for value in scored.values()
            if value["receipts"] >= min_candidate
            and value["pass_rate"] == 1.0
            and value["severe_errors"] == 0
            and value["incomplete_snapshots"] == 0
            and value["weak_delegations"] == 0
            and value["lead_review_unknown"] == 0
            and value["lead_review_legacy"] == 0
            and value["failed_checks"] == 0
            and value["task_checks_legacy"] == 0
            and value["corrected_receipts"] == 0
            and value.get(comparison_metric) is not None
        ]
        eligible.sort(key=lambda value: value[comparison_metric], reverse=True)
        total = sum(value["receipts"] for value in scored.values())
        winner = eligible[0] if eligible else None
        runner_up = eligible[1] if len(eligible) > 1 else None
        gain = None
        if winner and runner_up:
            baseline = runner_up[comparison_metric]
            gain = (winner[comparison_metric] - baseline) / max(baseline, 0.0001)
        blockers = []
        if total < min_total:
            blockers.append(f"need_{min_total - total}_more_receipts")
        if winner is None or runner_up is None:
            blockers.append("fewer_than_two_passing_candidates")
        elif gain is None or gain < margin:
            blockers.append("material_margin_not_met")
        # ``promoted`` is a legacy safety field and is deliberately never true:
        # this process has recommendation authority only.  A caller may review
        # ``recommended`` as a suggestion, but no saved policy is changed here.
        recommended = not blockers
        classes[task_class] = {
            "observed_receipts": observed_classes[task_class],
            "total_receipts": total,
            "excluded_receipts": observed_classes[task_class] - total,
            "comparison_metric": comparison_metric,
            "candidates": scored,
            "recommendation": {
                "promoted": False,
                "recommended": recommended,
                "recommendation_only": True,
                "model": winner["model"] if recommended else None,
                "thinking": winner["thinking"] if recommended else None,
                "material_gain": round(gain, 4) if gain is not None else None,
                "blockers": blockers,
            },
        }

    qualified_count = sum(sum(len(items) for items in candidates.values()) for candidates in grouped.values())
    limitations = [
        "runtime observations are observational and do not establish causal savings",
        "recommendations do not modify saved routes",
        "subscription usage is unknown unless an explicit measured value was recorded",
        "token and cost diagnostics are not used as subscription usage",
    ]
    if any(lead_review_status(item) in {"unknown", "legacy"} for item in bases):
        limitations.append("legacy or unreviewed receipts remain unknown for independent lead review")
    if any(corrections.values()):
        limitations.append("owner corrections are linked events applied only as derived scoring state")
    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "receipt_count": len(bases),
        "qualified_receipt_count": qualified_count,
        "excluded_receipt_count": len(bases) - qualified_count,
        "correction_event_count": sum(len(values) for values in corrections.values()),
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "window_days": 30,
        "minimum_total_per_class": min_total,
        "minimum_per_candidate": min_candidate,
        "material_margin": margin,
        "recommendation_only": True,
        "limitations": limitations,
        "task_classes": classes,
    }


def weekly_summary(entries: list[dict], *, days: int = 7, as_of: datetime | None = None) -> dict:
    """Build a compact digest with bounded evidence and explicit limitations."""
    bases = _base_receipts(entries)
    corrections = correction_map(entries)
    qualified = [
        effective_item(item, corrections.get(item.get("receipt_id"), []))
        for item in bases
        if exclusion_reason(item) is None
    ]
    overall = score(qualified)
    evidence_classes: Counter[str] = Counter(item.get("task_class", "unknown") for item in bases)
    routes: dict[str, dict] = {}
    route_items: dict[str, list[dict]] = defaultdict(list)
    for item in qualified:
        model, thinking = resolved_route(item)
        route_items[f"{model}/{thinking}"].append(item)
    for route, items in sorted(route_items.items()):
        route_score = score(items)
        routes[route] = {
            "receipts": route_score["receipts"],
            "accepted_outcomes": route_score["accepted_outcomes"],
            "failed_outcomes": route_score["failures"],
            "unknown_acceptance": route_score["unknown_acceptance"],
            "attempts": route_score["attempts"],
            "rework_seconds": route_score["rework_seconds"],
            "subscription_usage_total": route_score["subscription_usage_total"],
            "accepted_outcomes_per_subscription_usage": route_score[
                "accepted_outcomes_per_subscription_usage"
            ],
        }
    limitations = [
        "runtime observations are observational and do not establish causal savings",
        "subscription usage is unknown unless an explicit measured value was recorded",
        "token and cost diagnostics are not used as subscription usage",
        "this digest is read-only evidence, not a route promotion",
    ]
    if overall["subscription_usage_unknown_receipts"]:
        limitations.append("some receipts have unknown subscription usage, so usage efficiency is incomplete")
    # Include excluded and legacy rows in coverage warnings.  The route metrics
    # intentionally score only qualified rows, but a digest must not make
    # missing review/check evidence disappear merely because capability proof
    # was also missing.
    lead_unknown = sum(lead_review_status(item) == "unknown" for item in bases)
    lead_legacy = sum(lead_review_status(item) == "legacy" for item in bases)
    checks_unknown = sum(task_checks_status(item) == "unknown" for item in bases)
    checks_legacy = sum(task_checks_status(item) == "legacy" for item in bases)
    if lead_unknown or lead_legacy or checks_unknown or checks_legacy:
        limitations.append("legacy or unreviewed receipts remain unknown for independent lead review")
    if any(corrections.values()):
        limitations.append("owner corrections are linked events and count rework in derived scoring")
    timestamp = as_of or datetime.now(timezone.utc)
    return {
        "schema_version": "1.0",
        "summary_kind": "weekly_routing_digest",
        "as_of": timestamp.astimezone(timezone.utc).isoformat(),
        "window_days": days,
        "recommendation_only": True,
        "evidence": {
            "receipt_count": len(bases),
            "qualified_receipt_count": len(qualified),
            "completed_receipt_count": sum(item.get("lifecycle_state") == "completed" for item in bases),
            "accepted_outcomes": overall["accepted_outcomes"],
            "failed_outcomes": overall["failures"],
            "unknown_acceptance": overall["unknown_acceptance"],
            "attempts": overall["attempts"],
            "rework_seconds": overall["rework_seconds"],
            "correction_event_count": overall["correction_events"],
            "corrected_receipt_count": overall["corrected_receipts"],
            "subscription_usage_total": overall["subscription_usage_total"],
            "accepted_outcomes_per_subscription_usage": overall[
                "accepted_outcomes_per_subscription_usage"
            ],
            "subscription_usage_observed_receipts": overall["subscription_usage_observed_receipts"],
            "subscription_usage_unknown_receipts": overall["subscription_usage_unknown_receipts"],
            "lead_review_unknown_receipts": lead_unknown,
            "lead_review_legacy_receipts": lead_legacy,
            "task_checks_unknown_receipts": checks_unknown,
            "task_checks_legacy_receipts": checks_legacy,
            "task_classes_observed": dict(sorted(evidence_classes.items())),
        },
        "routes": routes,
        "limitations": limitations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path.home() / ".codex/routing/receipts.jsonl")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--minimum-total", type=int, default=30)
    parser.add_argument("--minimum-per-candidate", type=int, default=5)
    parser.add_argument("--material-margin", type=float, default=0.10)
    parser.add_argument("--weekly-summary", "--summary", action="store_true", dest="weekly_summary")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.days < 1:
        raise SystemExit("days must be at least one")
    entries = load_entries(args.store.expanduser(), args.days)
    if args.weekly_summary:
        result = weekly_summary(entries, days=args.days)
        result["window_days"] = args.days
    else:
        result = evaluate(
            entries,
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
