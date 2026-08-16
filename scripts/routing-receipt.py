#!/usr/bin/env python3
"""Record redacted CAPS worker routing receipts with recoverable lifecycle state.

The conductor starts a receipt before spawn, binds it to a one-way hash after
spawn, and then finishes or abandons it. Raw prompts, answers, worker
references, paths, and proof content are intentionally excluded.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = "1.2"
TASK_CLASSES = {
    "coding", "research_strategy", "computer_use", "content_polish",
    "transformation", "proof_review",
}
ROUTE_REASONS = {"default", "policy", "canary", "override", "bakeoff"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def default_store() -> Path:
    configured = os.environ.get("CAPS_ROUTING_RECEIPTS")
    return Path(configured).expanduser() if configured else Path.home() / ".codex/routing/receipts.jsonl"


def pending_dir(store: Path) -> Path:
    return store.parent / "pending"


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


@contextmanager
def receipt_lock(store: Path) -> Iterator[None]:
    directory = pending_dir(store)
    ensure_directory(directory)
    lock_path = directory / ".receipt-lifecycle.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def atomic_write_json(path: Path, payload: dict) -> None:
    ensure_directory(path.parent)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def append_jsonl(path: Path, payload: dict) -> None:
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def receipt_already_recorded(store: Path, receipt_id: str) -> bool:
    if not store.exists():
        return False
    with store.open(encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("receipt_id") == receipt_id:
                    return True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return False


def pending_path(store: Path, receipt_id: str) -> Path:
    try:
        uuid.UUID(receipt_id)
    except ValueError as error:
        raise SystemExit("receipt-id must be a UUID") from error
    return pending_dir(store) / f"{receipt_id}.json"


def load_pending(store: Path, receipt_id: str) -> tuple[Path, dict]:
    source = pending_path(store, receipt_id)
    if not source.exists():
        raise SystemExit(f"pending receipt not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"pending receipt is unreadable: {source}: {error}") from error
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(
            f"legacy pending receipt requires receipt-doctor.py: {source}"
        )
    if payload.get("lifecycle_state") != "pending":
        raise SystemExit(f"receipt is not pending: {receipt_id}")
    return source, payload


def sha256_label(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_digest(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.lower()
    if candidate.startswith("sha256:"):
        candidate = candidate[7:]
    if len(candidate) != 64 or any(character not in "0123456789abcdef" for character in candidate):
        raise SystemExit("capability-snapshot-digest must be a SHA-256 hex digest")
    return f"sha256:{candidate}"


def resolve_route(args: argparse.Namespace) -> tuple[str, str, str, str]:
    requested_model = args.requested_model or args.model
    requested_thinking = args.requested_thinking or args.thinking
    resolved_model = args.resolved_model or args.model or requested_model
    resolved_thinking = args.resolved_thinking or args.thinking or requested_thinking
    if args.model and args.requested_model and args.model != args.requested_model:
        raise SystemExit("--model conflicts with --requested-model")
    if args.thinking and args.requested_thinking and args.thinking != args.requested_thinking:
        raise SystemExit("--thinking conflicts with --requested-thinking")
    if not all((requested_model, requested_thinking, resolved_model, resolved_thinking)):
        raise SystemExit(
            "start requires requested/resolved model and thinking; legacy --model/--thinking may supply both"
        )
    return requested_model, requested_thinking, resolved_model, resolved_thinking


def cmd_start(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    requested_model, requested_thinking, resolved_model, resolved_thinking = resolve_route(args)
    capability_digest = normalize_digest(args.capability_snapshot_digest)
    receipt_id = str(uuid.uuid4())
    payload = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "started_at": now().isoformat(),
        "finished_at": None,
        "lifecycle_state": "pending",
        "binding_state": "unbound",
        "bound_at": None,
        "worker_kind": args.worker_kind,
        "worker_ref_hash": None,
        "parent_receipt_id": args.parent_receipt_id,
        "delegation_depth": args.delegation_depth,
        "task_class": args.task_class,
        "requested_model": requested_model,
        "requested_thinking": requested_thinking,
        "resolved_model": resolved_model,
        "resolved_thinking": resolved_thinking,
        "capability_snapshot_digest": capability_digest,
        "capability_verified": False,
        "routing_mode": args.routing_mode,
        "route_reason": args.route_reason,
        "quality_gate_id": args.quality_gate_id,
        "task_snapshot_complete": args.task_snapshot_complete,
        "experiment_id": args.experiment_id,
        "profile_version": args.profile_version,
        "host": socket.gethostname(),
        "observability_state": "complete",
        "observability_failure_code": None,
        "learning_eligibility": "ineligible",
        "elapsed_seconds": None,
        "quality_passed": None,
        "gate_result": None,
        "delegation_quality": None,
        "outcome": None,
        "severe_error": False,
        "retry_count": 0,
        "rework_seconds": 0.0,
        "proof_refs": [],
        "failure_code": None,
        "escalation_reason": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "evidence_kind": "runtime_observation",
    }
    target = pending_path(store, receipt_id)
    with receipt_lock(store):
        if target.exists():
            raise SystemExit(f"pending receipt already exists: {target}")
        atomic_write_json(target, payload)
    print(receipt_id)


def cmd_bind(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    if not args.worker_ref:
        raise SystemExit("worker-ref cannot be empty")
    with receipt_lock(store):
        source, payload = load_pending(store, args.receipt_id)
        if payload["binding_state"] == "bound":
            raise SystemExit(f"receipt is already bound: {args.receipt_id}")
        payload.update({
            "binding_state": "bound",
            "bound_at": now().isoformat(),
            "worker_ref_hash": sha256_label(args.worker_ref),
        })
        atomic_write_json(source, payload)
    print(json.dumps({"status": "bound", "receipt_id": args.receipt_id}, sort_keys=True))


def cmd_degrade(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    with receipt_lock(store):
        source, payload = load_pending(store, args.receipt_id)
        payload.update({
            "observability_state": "degraded",
            "observability_failure_code": args.failure_code,
            "learning_eligibility": "ineligible",
        })
        atomic_write_json(source, payload)
    print(json.dumps({"status": "observability_degraded", "receipt_id": args.receipt_id}, sort_keys=True))


def is_learning_eligible(payload: dict) -> bool:
    # Outcome quality is evidence, not an eligibility gate. Completed failures,
    # partial/failed delegations, retries, and rework must remain in calibration
    # so the evaluator cannot learn only from successful workers.
    return all((
        payload["lifecycle_state"] == "completed",
        payload["binding_state"] == "bound",
        payload["capability_verified"],
        payload["observability_state"] == "complete",
        payload["task_snapshot_complete"],
    ))


def finalize(store: Path, receipt_id: str, values: dict, require_bound: bool) -> str:
    with receipt_lock(store):
        source = pending_path(store, receipt_id)
        if receipt_already_recorded(store, receipt_id):
            if source.exists():
                source.unlink()
                fsync_directory(source.parent)
            return "already_recorded"
        source, payload = load_pending(store, receipt_id)
        if require_bound and payload["binding_state"] != "bound":
            raise SystemExit(f"worker receipt must be bound before finish: {receipt_id}")
        if values.get("capability_verified") and not payload.get("capability_snapshot_digest"):
            raise SystemExit("capability verification requires a capability snapshot digest")
        finished = now()
        started = datetime.fromisoformat(payload["started_at"])
        payload.update(values)
        payload.update({
            "finished_at": finished.isoformat(),
            "elapsed_seconds": round(max((finished - started).total_seconds(), 0.001), 3),
        })
        payload["learning_eligibility"] = "eligible" if is_learning_eligible(payload) else "ineligible"
        append_jsonl(store, payload)
        source.unlink()
        fsync_directory(source.parent)
    return "recorded"


def final_values(args: argparse.Namespace) -> dict:
    outcome = args.outcome
    return {
        "lifecycle_state": "completed",
        "quality_passed": outcome == "pass",
        "gate_result": outcome,
        "delegation_quality": args.delegation_quality,
        "outcome": outcome,
        "capability_verified": args.capability_verified,
        "severe_error": args.severe_error,
        "retry_count": args.retry_count,
        "rework_seconds": args.rework_seconds,
        "proof_refs": args.proof_ref,
        "failure_code": args.failure_code,
        "escalation_reason": args.escalation_reason,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
    }


def cmd_finish(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    if args.outcome == "abandoned":
        values = abandon_values(args, args.failure_code or "abandoned")
        status = finalize(store, args.receipt_id, values, require_bound=False)
    else:
        status = finalize(store, args.receipt_id, final_values(args), require_bound=True)
    print(json.dumps({"status": status, "receipt_id": args.receipt_id, "store": str(store)}, sort_keys=True))


def abandon_values(args: argparse.Namespace, failure_code: str) -> dict:
    return {
        "lifecycle_state": "abandoned",
        "quality_passed": False,
        "gate_result": "abandoned",
        "delegation_quality": args.delegation_quality,
        "outcome": "abandoned",
        "capability_verified": False,
        "severe_error": args.severe_error,
        "retry_count": args.retry_count,
        "rework_seconds": args.rework_seconds,
        "proof_refs": args.proof_ref,
        "failure_code": failure_code,
        "escalation_reason": args.escalation_reason,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
    }


def cmd_abandon(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    status = finalize(store, args.receipt_id, abandon_values(args, args.failure_code), require_bound=False)
    print(json.dumps({"status": status, "receipt_id": args.receipt_id, "store": str(store)}, sort_keys=True))


def add_terminal_arguments(command: argparse.ArgumentParser, *, include_outcome: bool) -> None:
    command.add_argument("--receipt-id", required=True)
    if include_outcome:
        command.add_argument("--outcome", required=True, choices=("pass", "fail", "abandoned"))
        command.add_argument("--capability-verified", action="store_true")
    command.add_argument("--delegation-quality", default="failed", choices=("complete", "partial", "failed"))
    command.add_argument("--severe-error", action="store_true")
    command.add_argument("--retry-count", type=int, default=0)
    command.add_argument("--rework-seconds", type=float, default=0.0)
    command.add_argument("--proof-ref", action="append", default=[])
    command.add_argument("--failure-code")
    command.add_argument("--escalation-reason")
    command.add_argument("--input-tokens", type=int)
    command.add_argument("--output-tokens", type=int)
    command.add_argument("--estimated-cost-usd", type=float)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--store", type=Path, default=default_store())
    sub = result.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--task-class", required=True, choices=sorted(TASK_CLASSES))
    start.add_argument("--requested-model")
    start.add_argument("--requested-thinking")
    start.add_argument("--resolved-model")
    start.add_argument("--resolved-thinking")
    start.add_argument("--model", help=argparse.SUPPRESS)
    start.add_argument("--thinking", help=argparse.SUPPRESS)
    start.add_argument("--worker-kind", default="subagent", choices=("subagent", "durable_thread"))
    start.add_argument("--parent-receipt-id")
    start.add_argument("--delegation-depth", type=int, default=1)
    start.add_argument("--capability-snapshot-digest", required=True)
    start.add_argument("--routing-mode", default="direct", choices=("direct", "probe_then_escalate"))
    start.add_argument("--route-reason", required=True, choices=sorted(ROUTE_REASONS))
    start.add_argument("--quality-gate-id", required=True)
    start.add_argument("--task-snapshot-complete", action="store_true")
    start.add_argument("--experiment-id")
    start.add_argument("--profile-version", required=True)
    start.set_defaults(handler=cmd_start)

    bind = sub.add_parser("bind")
    bind.add_argument("--receipt-id", required=True)
    bind.add_argument("--worker-ref", required=True)
    bind.set_defaults(handler=cmd_bind)

    degrade = sub.add_parser("degrade")
    degrade.add_argument("--receipt-id", required=True)
    degrade.add_argument("--failure-code", required=True)
    degrade.set_defaults(handler=cmd_degrade)

    finish = sub.add_parser("finish")
    add_terminal_arguments(finish, include_outcome=True)
    finish.set_defaults(handler=cmd_finish)

    abandon = sub.add_parser("abandon")
    add_terminal_arguments(abandon, include_outcome=False)
    abandon.set_defaults(handler=cmd_abandon, failure_code="abandoned")

    spawn_failed = sub.add_parser("spawn-failed")
    add_terminal_arguments(spawn_failed, include_outcome=False)
    spawn_failed.set_defaults(handler=cmd_abandon, failure_code="spawn_failed")
    return result


def validate_args(args: argparse.Namespace) -> None:
    if getattr(args, "quality_gate_id", None) and len(args.quality_gate_id) > 80:
        raise SystemExit("quality-gate-id must be a short label, not private task content")
    if getattr(args, "worker_kind", None):
        worker_kind = args.worker_kind
        if len(worker_kind) > 64 or not worker_kind[0].isalpha() or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in worker_kind
        ):
            raise SystemExit("worker-kind must be a short lowercase label")
    if getattr(args, "parent_receipt_id", None):
        try:
            uuid.UUID(args.parent_receipt_id)
        except ValueError as error:
            raise SystemExit("parent-receipt-id must be a UUID") from error
    if not 0 <= getattr(args, "delegation_depth", 0) <= 2:
        raise SystemExit("delegation-depth must be between 0 and 2")
    for name in ("failure_code", "observability_failure_code"):
        value = getattr(args, name, None)
        if value and len(value) > 80:
            raise SystemExit(f"{name.replace('_', '-')} must be a short label")
    if getattr(args, "escalation_reason", None) and len(args.escalation_reason) > 120:
        raise SystemExit("escalation-reason must be a short label, not private task content")
    if getattr(args, "retry_count", 0) < 0 or getattr(args, "rework_seconds", 0) < 0:
        raise SystemExit("retry and rework values cannot be negative")
    for name in ("input_tokens", "output_tokens", "estimated_cost_usd"):
        value = getattr(args, name, None)
        if value is not None and value < 0:
            raise SystemExit(f"{name.replace('_', '-')} cannot be negative")


def main() -> None:
    args = parser().parse_args()
    validate_args(args)
    args.handler(args)


if __name__ == "__main__":
    main()
