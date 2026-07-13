#!/usr/bin/env python3
"""Start and finish redacted CAPS runtime routing receipts.

The conductor starts a receipt immediately before creating a worker and finishes
it only after reviewing the worker's quality gate. Raw prompts, answers, paths,
and proof content are intentionally excluded.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


MODELS = {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}
THINKING = {"low", "medium", "high", "xhigh", "max", "ultra"}
TASK_CLASSES = {
    "coding", "research_strategy", "computer_use", "content_polish",
    "transformation", "proof_review",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def default_store() -> Path:
    configured = os.environ.get("CAPS_ROUTING_RECEIPTS")
    return Path(configured).expanduser() if configured else Path.home() / ".codex/routing/receipts.jsonl"


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def pending_dir(store: Path) -> Path:
    return store.parent / "pending"


def cmd_start(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    receipt_id = str(uuid.uuid4())
    payload = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "started_at": now().isoformat(),
        "task_class": args.task_class,
        "model": args.model,
        "thinking": args.thinking,
        "routing_mode": args.routing_mode,
        "route_reason": args.route_reason,
        "quality_gate_id": args.quality_gate_id,
        "experiment_id": args.experiment_id,
        "profile_version": args.profile_version,
        "host": socket.gethostname(),
    }
    directory = pending_dir(store)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{receipt_id}.json"
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
    print(receipt_id)


def cmd_finish(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    source = pending_dir(store) / f"{args.receipt_id}.json"
    if not source.exists():
        raise SystemExit(f"pending receipt not found: {source}")
    payload = json.loads(source.read_text())
    finished = now()
    started = datetime.fromisoformat(payload["started_at"])
    payload.update({
        "finished_at": finished.isoformat(),
        "elapsed_seconds": round(max((finished - started).total_seconds(), 0.001), 3),
        "quality_passed": args.outcome == "pass",
        "outcome": args.outcome,
        "severe_error": args.severe_error,
        "retry_count": args.retry_count,
        "rework_seconds": args.rework_seconds,
        "proof_refs": args.proof_ref,
        "failure_code": args.failure_code,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
        "evidence_kind": "runtime_observation",
    })
    append_jsonl(store, payload)
    source.unlink()
    print(json.dumps({"status": "recorded", "receipt_id": args.receipt_id, "store": str(store)}))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--store", type=Path, default=default_store())
    sub = result.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--task-class", required=True, choices=sorted(TASK_CLASSES))
    start.add_argument("--model", required=True, choices=sorted(MODELS))
    start.add_argument("--thinking", required=True, choices=sorted(THINKING))
    start.add_argument("--routing-mode", default="direct", choices=("direct", "probe_then_escalate"))
    start.add_argument("--route-reason", required=True, choices=("default", "policy", "canary", "override"))
    start.add_argument("--quality-gate-id", required=True)
    start.add_argument("--experiment-id")
    start.add_argument("--profile-version", required=True)
    start.set_defaults(handler=cmd_start)

    finish = sub.add_parser("finish")
    finish.add_argument("--receipt-id", required=True)
    finish.add_argument("--outcome", required=True, choices=("pass", "fail", "abandoned"))
    finish.add_argument("--severe-error", action="store_true")
    finish.add_argument("--retry-count", type=int, default=0)
    finish.add_argument("--rework-seconds", type=float, default=0.0)
    finish.add_argument("--proof-ref", action="append", default=[])
    finish.add_argument("--failure-code")
    finish.add_argument("--input-tokens", type=int)
    finish.add_argument("--output-tokens", type=int)
    finish.add_argument("--estimated-cost-usd", type=float)
    finish.set_defaults(handler=cmd_finish)
    return result


def main() -> None:
    args = parser().parse_args()
    if getattr(args, "quality_gate_id", None) and len(args.quality_gate_id) > 80:
        raise SystemExit("quality-gate-id must be a short label, not private task content")
    if getattr(args, "retry_count", 0) < 0 or getattr(args, "rework_seconds", 0) < 0:
        raise SystemExit("retry and rework values cannot be negative")
    args.handler(args)


if __name__ == "__main__":
    main()
