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
import re
import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = "1.2"
RECEIPT_EVENT = "receipt"
CORRECTION_EVENT = "correction"
TASK_CLASSES = {
    "coding", "research_strategy", "computer_use", "content_polish",
    "transformation", "proof_review",
}
ROUTE_REASONS = {"default", "policy", "canary", "override", "bakeoff"}
SAFE_LABEL_CHARS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


def safe_label(value: str | None, field: str, *, max_length: int = 80) -> str | None:
    """Validate a public-safe metadata label without retaining source text.

    Labels deliberately exclude whitespace, path separators, and control
    characters.  They can identify a gate, check, proof, or blocker, but they
    cannot carry a prompt, transcript, secret, or private filesystem path.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise SystemExit(f"{field} must be a short metadata label")
    if ".." in value or not SAFE_LABEL_CHARS.fullmatch(value):
        raise SystemExit(f"{field} must be a public-safe metadata label")
    return value


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
                if (
                    payload.get("receipt_id") == receipt_id
                    and payload.get("event_type", RECEIPT_EVENT) == RECEIPT_EVENT
                ):
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


def iter_store(store: Path) -> Iterator[dict]:
    """Yield valid JSON objects from the single append-only receipt store."""
    if not store.exists():
        return
    with store.open(encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    # The evaluator reports malformed rows with line context;
                    # lookup helpers should not turn a bad row into a write.
                    continue
                if isinstance(payload, dict):
                    yield payload
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def parse_check(value: str, field: str = "task-check") -> dict:
    """Parse ``label[=pass|fail]`` into redacted check metadata."""
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{field} must be a metadata label")
    label = value
    passed = True
    if "=" in value:
        label, result = value.rsplit("=", 1)
        if result not in {"pass", "fail"}:
            raise SystemExit(f"{field} status must be pass or fail")
        passed = result == "pass"
    safe_label(label, field)
    return {"label": label, "passed": passed}


def parse_lead_review(args: argparse.Namespace) -> bool | None:
    status = getattr(args, "lead_review_status", None)
    marker = getattr(args, "lead_reviewed", None)
    if status is not None:
        status_value = status.lower()
        if status_value not in {"pass", "fail", "unknown", "true", "false"}:
            raise SystemExit("lead-review must be pass, fail, unknown, true, or false")
        status_marker = {"pass": True, "true": True, "fail": False, "false": False, "unknown": None}[status_value]
        if marker is not None and marker != status_marker:
            raise SystemExit("lead-review conflicts with lead-reviewed")
        marker = status_marker
    return marker


def parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"true", "yes", "pass", "passed", "1"}:
        return True
    if normalized in {"false", "no", "fail", "failed", "0"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def parse_task_checks(args: argparse.Namespace) -> tuple[list[dict], bool | None]:
    raw_checks = getattr(args, "task_check", None) or []
    checks = [parse_check(value) for value in raw_checks]
    explicit = getattr(args, "checks_passed", None)
    inferred = all(item["passed"] for item in checks) if checks else None
    if explicit is True and inferred is False:
        raise SystemExit("checks-passed cannot pass when a task check failed")
    if explicit is None:
        explicit = inferred
    return checks, explicit


def explicit_acceptance_requested(args: argparse.Namespace) -> bool:
    return bool(
        getattr(args, "task_check", None)
        or getattr(args, "checks_passed", None) is not None
        or getattr(args, "lead_reviewed", None) is not None
        or getattr(args, "lead_review_status", None) is not None
    )


def validate_acceptance_args(args: argparse.Namespace) -> None:
    """Require both independent acceptance inputs for a newly explicit pass."""
    if getattr(args, "outcome", None) != "pass" or not explicit_acceptance_requested(args):
        return
    _, checks_passed = parse_task_checks(args)
    if parse_lead_review(args) is not True:
        raise SystemExit("a passing receipt requires an explicit independent lead review")
    if checks_passed is not True:
        raise SystemExit("a passing receipt requires all task-specific checks to pass")


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
        "event_type": RECEIPT_EVENT,
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
        # New receipts carry an explicit independent lead-review marker.  It
        # stays null until review is recorded; rows from older writers simply
        # lack this field and remain legacy/unknown to the evaluator.
        "lead_reviewed": None,
        "task_checks": [],
        "task_checks_passed": None,
        "attempts": 1,
        "severe_error": False,
        "retry_count": 0,
        "rework_seconds": 0.0,
        "correction_count": 0,
        "owner_correction_count": 0,
        "proof_refs": [],
        "failure_code": None,
        "escalation_reason": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        # Subscription units are intentionally separate from token and cost
        # diagnostics.  Unknown usage remains null; it is never inferred.
        "subscription_usage": None,
        "subscription_usage_source": None,
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
    task_checks, task_checks_passed = parse_task_checks(args)
    lead_reviewed = parse_lead_review(args)
    return {
        "lifecycle_state": "completed",
        "quality_passed": outcome == "pass",
        "gate_result": outcome,
        "delegation_quality": args.delegation_quality,
        "outcome": outcome,
        "lead_reviewed": lead_reviewed,
        "task_checks": task_checks,
        "task_checks_passed": task_checks_passed,
        "attempts": args.attempts if args.attempts is not None else args.retry_count + 1,
        "capability_verified": args.capability_verified,
        "severe_error": args.severe_error,
        "retry_count": args.retry_count,
        "rework_seconds": args.rework_seconds,
        "correction_count": 0,
        "owner_correction_count": 0,
        "proof_refs": args.proof_ref,
        "failure_code": args.failure_code,
        "escalation_reason": args.escalation_reason,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
        "subscription_usage": args.subscription_usage,
        "subscription_usage_source": args.subscription_usage_source,
    }


def cmd_finish(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    validate_acceptance_args(args)
    if args.outcome == "abandoned":
        values = abandon_values(args, args.failure_code or "abandoned")
        status = finalize(store, args.receipt_id, values, require_bound=False)
    else:
        status = finalize(store, args.receipt_id, final_values(args), require_bound=True)
    print(json.dumps({"status": status, "receipt_id": args.receipt_id, "store": str(store)}, sort_keys=True))


def abandon_values(args: argparse.Namespace, failure_code: str) -> dict:
    task_checks, task_checks_passed = parse_task_checks(args)
    lead_reviewed = parse_lead_review(args)
    return {
        "lifecycle_state": "abandoned",
        "quality_passed": False,
        "gate_result": "abandoned",
        "delegation_quality": args.delegation_quality,
        "outcome": "abandoned",
        "lead_reviewed": lead_reviewed,
        "task_checks": task_checks,
        "task_checks_passed": task_checks_passed,
        "attempts": args.attempts if args.attempts is not None else args.retry_count + 1,
        "capability_verified": False,
        "severe_error": args.severe_error,
        "retry_count": args.retry_count,
        "rework_seconds": args.rework_seconds,
        "correction_count": 0,
        "owner_correction_count": 0,
        "proof_refs": args.proof_ref,
        "failure_code": failure_code,
        "escalation_reason": args.escalation_reason,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "estimated_cost_usd": args.estimated_cost_usd,
        "subscription_usage": args.subscription_usage,
        "subscription_usage_source": args.subscription_usage_source,
    }


def cmd_abandon(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    status = finalize(store, args.receipt_id, abandon_values(args, args.failure_code), require_bound=False)
    print(json.dumps({"status": status, "receipt_id": args.receipt_id, "store": str(store)}, sort_keys=True))


def recorded_receipt(store: Path, receipt_id: str) -> dict | None:
    for payload in iter_store(store):
        if (
            payload.get("receipt_id") == receipt_id
            and payload.get("event_type", RECEIPT_EVENT) == RECEIPT_EVENT
        ):
            return payload
    return None


def correction_identity(args: argparse.Namespace) -> str:
    identity = args.idempotency_key or args.correction_id
    if not identity:
        raise SystemExit("correction requires --idempotency-key or --correction-id")
    safe_label(identity, "idempotency-key", max_length=160)
    return identity


def correction_accepted_after(args: argparse.Namespace) -> bool:
    values = []
    if args.accepted is not None:
        values.append(args.accepted)
    if args.correction_outcome is not None:
        values.append(args.correction_outcome == "pass")
    if len(values) > 1 and values[0] != values[1]:
        raise SystemExit("correction acceptance flags conflict")
    # A correction is a later owner finding that an accepted output should no
    # longer count.  Keeping false as the default makes the safe operation
    # explicit in the resulting event while still permitting a monotonic
    # acceptance audit with --accepted.
    return values[0] if values else False


def correction_already_recorded(store: Path, receipt_id: str, identity_hash: str, correction_id: str) -> dict | None:
    for payload in iter_store(store):
        if payload.get("event_type") != CORRECTION_EVENT:
            continue
        if payload.get("receipt_id") != receipt_id:
            continue
        if payload.get("idempotency_key_hash") == identity_hash or payload.get("correction_id") == correction_id:
            return payload
    return None


def receipt_was_accepted(payload: dict) -> bool:
    """Read the independent acceptance markers without treating omissions as pass."""
    if (
        payload.get("lifecycle_state") != "completed"
        or payload.get("quality_passed") is not True
        or payload.get("outcome") != "pass"
        or payload.get("gate_result", "pass") != "pass"
        or payload.get("severe_error", False)
    ):
        return False
    review = payload.get("lead_reviewed")
    if review is not True:
        review = payload.get("lead_review")
        if isinstance(review, dict):
            review = review.get("passed", review.get("reviewed"))
        if not (review is True or (isinstance(review, str) and review.lower() in {"pass", "passed", "true"})):
            return False
    checks = payload.get("task_checks_passed")
    if checks is None:
        checks = payload.get("checks_passed", payload.get("acceptance_checks_passed"))
    if checks is not True:
        details = payload.get("task_checks", payload.get("acceptance_checks", payload.get("checks")))
        if isinstance(details, dict):
            details = list(details.values())
        if not isinstance(details, list) or not details:
            return False
        if not all(
            value is True or (isinstance(value, dict) and value.get("passed") is True)
            for value in details
        ):
            return False
    return True


def cmd_correct(args: argparse.Namespace) -> None:
    store = args.store.expanduser()
    receipt_id = args.receipt_id
    try:
        uuid.UUID(receipt_id)
    except ValueError as error:
        raise SystemExit("receipt-id must be a UUID") from error
    identity = correction_identity(args)
    identity_hash = sha256_label(identity)
    correction_id = args.correction_id or str(uuid.uuid4())
    safe_label(correction_id, "correction-id", max_length=160)
    accepted_after = correction_accepted_after(args)
    if args.rework_seconds < 0:
        raise SystemExit("rework-seconds cannot be negative")
    if args.attempts_added < 0:
        raise SystemExit("attempts-added cannot be negative")
    if args.subscription_usage is not None and args.subscription_usage < 0:
        raise SystemExit("subscription-usage cannot be negative")
    if args.reason:
        safe_label(args.reason, "correction-reason", max_length=120)
    if args.subscription_usage_source:
        safe_label(args.subscription_usage_source, "subscription-usage-source")

    with receipt_lock(store):
        base = recorded_receipt(store, receipt_id)
        if base is None:
            raise SystemExit(f"recorded receipt not found: {receipt_id}")
        previous = correction_already_recorded(store, receipt_id, identity_hash, correction_id)
        if previous is not None:
            print(json.dumps({
                "status": "already_recorded",
                "receipt_id": receipt_id,
                "correction_id": previous.get("correction_id", correction_id),
                "store": str(store),
            }, sort_keys=True))
            return

        event = {
            "schema_version": SCHEMA_VERSION,
            "event_type": CORRECTION_EVENT,
            "correction_id": correction_id,
            "idempotency_key_hash": identity_hash,
            "receipt_id": receipt_id,
            "corrected_at": now().isoformat(),
            "owner_correction": True,
            "accepted_before": receipt_was_accepted(base),
            "accepted_after": accepted_after,
            "rework_seconds": args.rework_seconds,
            "attempts_added": args.attempts_added,
            "reason": args.reason,
            "subscription_usage": args.subscription_usage,
            "subscription_usage_source": args.subscription_usage_source,
            "evidence_kind": "owner_correction",
        }
        append_jsonl(store, event)
    print(json.dumps({
        "status": "recorded",
        "receipt_id": receipt_id,
        "correction_id": correction_id,
        "store": str(store),
    }, sort_keys=True))


def compact_summary(store: Path, days: int) -> dict:
    """Return a bounded, read-only summary safe for a weekly digest."""
    # Importing the evaluator keeps one source of truth for correction
    # application and metrics without creating another persistence system.
    import importlib.util

    evaluator_path = Path(__file__).with_name("evaluate-routing-receipts.py")
    spec = importlib.util.spec_from_file_location("caps_receipt_evaluator", evaluator_path)
    if spec is None or spec.loader is None:
        raise SystemExit("unable to load receipt evaluator")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    entries = evaluator.load_entries(store, days)
    return evaluator.weekly_summary(entries, days=days)


def cmd_summary(args: argparse.Namespace) -> None:
    if args.days < 1:
        raise SystemExit("days must be at least one")
    print(json.dumps(compact_summary(args.store.expanduser(), args.days), indent=2, sort_keys=True))


def add_terminal_arguments(command: argparse.ArgumentParser, *, include_outcome: bool) -> None:
    command.add_argument("--receipt-id", required=True)
    if include_outcome:
        command.add_argument("--outcome", required=True, choices=("pass", "fail", "abandoned"))
        command.add_argument("--capability-verified", action="store_true")
    lead_review = command.add_mutually_exclusive_group()
    lead_review.add_argument(
        "--lead-reviewed", dest="lead_reviewed", nargs="?", const=True, type=parse_bool
    )
    lead_review.add_argument(
        "--no-lead-review", "--lead-review-failed",
        dest="lead_reviewed", action="store_false",
    )
    command.add_argument(
        "--lead-review", "--lead-review-status",
        dest="lead_review_status", nargs="?", const="pass",
        choices=("pass", "fail", "unknown", "true", "false"),
    )
    checks = command.add_mutually_exclusive_group()
    checks.add_argument(
        "--checks-passed", "--task-checks-passed",
        dest="checks_passed", action="store_true",
    )
    checks.add_argument(
        "--no-checks-passed", "--checks-failed",
        dest="checks_passed", action="store_false",
    )
    command.add_argument(
        "--task-check", "--acceptance-check", "--acceptance-checks", "--check", "--checks",
        dest="task_check", action="append", default=[],
        help="Public-safe task check label, optionally label=pass|fail.",
    )
    command.add_argument("--delegation-quality", default="failed", choices=("complete", "partial", "failed"))
    command.add_argument("--severe-error", action="store_true")
    command.add_argument("--retry-count", type=int, default=0)
    command.add_argument("--attempts", type=int)
    command.add_argument("--rework-seconds", type=float, default=0.0)
    command.add_argument("--proof-ref", action="append", default=[])
    command.add_argument("--failure-code")
    command.add_argument("--escalation-reason")
    command.add_argument("--input-tokens", type=int)
    command.add_argument("--output-tokens", type=int)
    command.add_argument("--estimated-cost-usd", type=float)
    command.add_argument(
        "--subscription-usage", "--available-usage", "--usage", type=float,
    )
    command.add_argument("--subscription-usage-source")
    command.set_defaults(lead_reviewed=None, checks_passed=None, lead_review_status=None)


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

    correct = sub.add_parser("correct", aliases=("correction",))
    correct.add_argument("--receipt-id", required=True)
    correct.add_argument("--correction-id")
    correct.add_argument("--idempotency-key")
    acceptance = correct.add_mutually_exclusive_group()
    acceptance.add_argument(
        "--accepted", "--accepted-after", dest="accepted", nargs="?", const=True, type=parse_bool,
    )
    acceptance.add_argument(
        "--not-accepted", "--not-accepted-after", dest="accepted", action="store_false",
    )
    correct.add_argument("--outcome", "--correction-outcome", dest="correction_outcome", choices=("pass", "fail"))
    correct.add_argument("--rework-seconds", type=float, default=0.0)
    correct.add_argument("--attempts-added", "--correction-attempts", type=int, default=1)
    correct.add_argument("--reason", "--correction-reason")
    correct.add_argument(
        "--subscription-usage", "--available-usage", "--usage", type=float,
    )
    correct.add_argument("--subscription-usage-source")
    correct.set_defaults(handler=cmd_correct, accepted=None)

    summary = sub.add_parser("summary", aliases=("weekly-summary",))
    summary.add_argument("--days", type=int, default=7)
    summary.set_defaults(handler=cmd_summary)
    return result


def validate_args(args: argparse.Namespace) -> None:
    quality_gate_id = getattr(args, "quality_gate_id", None)
    if quality_gate_id is not None and len(quality_gate_id) > 80:
        raise SystemExit("quality-gate-id must be a short label, not private task content")
    if quality_gate_id is not None:
        safe_label(quality_gate_id, "quality-gate-id")
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
        if value is not None:
            safe_label(value, name.replace("_", "-"))
    escalation_reason = getattr(args, "escalation_reason", None)
    if escalation_reason is not None and len(escalation_reason) > 120:
        raise SystemExit("escalation-reason must be a short label, not private task content")
    if escalation_reason is not None:
        safe_label(escalation_reason, "escalation-reason", max_length=120)
    profile_version = getattr(args, "profile_version", None)
    if profile_version is not None:
        safe_label(profile_version, "profile-version")
    experiment_id = getattr(args, "experiment_id", None)
    if experiment_id is not None:
        safe_label(experiment_id, "experiment-id")
    for proof_ref in getattr(args, "proof_ref", []) or []:
        safe_label(proof_ref, "proof-ref")
    for task_check in getattr(args, "task_check", []) or []:
        parse_check(task_check)
    if getattr(args, "retry_count", 0) < 0 or getattr(args, "rework_seconds", 0) < 0:
        raise SystemExit("retry and rework values cannot be negative")
    if getattr(args, "attempts", None) is not None and args.attempts < 1:
        raise SystemExit("attempts must be at least one")
    for name in ("input_tokens", "output_tokens", "estimated_cost_usd"):
        value = getattr(args, name, None)
        if value is not None and value < 0:
            raise SystemExit(f"{name.replace('_', '-')} cannot be negative")
    usage = getattr(args, "subscription_usage", None)
    if usage is not None and usage < 0:
        raise SystemExit("subscription-usage cannot be negative")
    usage_source = getattr(args, "subscription_usage_source", None)
    if usage_source:
        safe_label(usage_source, "subscription-usage-source")
    attempts_added = getattr(args, "attempts_added", None)
    if attempts_added is not None and attempts_added < 0:
        raise SystemExit("attempts-added cannot be negative")
    if getattr(args, "lead_review_status", None) is not None:
        parse_lead_review(args)


def main() -> None:
    args = parser().parse_args()
    validate_args(args)
    args.handler(args)


if __name__ == "__main__":
    main()
