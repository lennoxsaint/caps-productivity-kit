#!/usr/bin/env python3
"""Audit CAPS pending routing receipts and quarantine unresolved legacy state.

The doctor never guesses whether a worker passed, failed, or finished. Current
pending receipts remain pending for an operator to finish or abandon. Legacy
pending files cannot prove their lifecycle and are preserved byte-for-byte in
the legacy_pending_unresolved quarantine.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def default_store() -> Path:
    configured = os.environ.get("CAPS_ROUTING_RECEIPTS")
    return Path(configured).expanduser() if configured else Path.home() / ".codex/routing/receipts.jsonl"


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def quarantine_legacy(source: Path, store: Path, dry_run: bool) -> tuple[str, str | None]:
    target_directory = store.parent / "quarantine" / "legacy_pending_unresolved"
    target = target_directory / source.name
    if dry_run:
        return "would_quarantine", str(target)
    target_directory.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return "quarantine_conflict", str(target)
    os.replace(source, target)
    fsync_directory(source.parent)
    fsync_directory(target_directory)
    return "quarantined", str(target)


def audit(store: Path, current_time: datetime, stale_after_seconds: float, dry_run: bool) -> dict:
    directory = store.parent / "pending"
    findings = []
    if not directory.exists():
        return {
            "schema_version": "1.0",
            "status": "ok",
            "pending_count": 0,
            "legacy_quarantined_count": 0,
            "findings": findings,
        }

    lock_path = directory / ".receipt-lifecycle.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        for source in sorted(directory.glob("*.json")):
            finding = {"file": str(source)}
            try:
                payload = json.loads(source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                finding.update({"status": "invalid_pending_receipt", "action": "manual_review", "error": str(error)})
                findings.append(finding)
                continue

            schema_version = payload.get("schema_version")
            finding["receipt_id"] = payload.get("receipt_id")
            if schema_version != "1.2":
                action, target = quarantine_legacy(source, store, dry_run)
                finding.update({
                    "status": "legacy_pending_unresolved",
                    "schema_version": schema_version,
                    "action": action,
                    "quarantine_path": target,
                })
                findings.append(finding)
                continue

            lifecycle_state = payload.get("lifecycle_state")
            binding_state = payload.get("binding_state")
            if lifecycle_state != "pending" or binding_state not in {"bound", "unbound"}:
                finding.update({
                    "status": "invalid_lifecycle_state",
                    "lifecycle_state": lifecycle_state,
                    "binding_state": binding_state,
                    "action": "manual_review",
                })
                findings.append(finding)
                continue
            try:
                age_seconds = max((current_time - parse_time(payload["started_at"])).total_seconds(), 0.0)
            except (KeyError, TypeError, ValueError) as error:
                finding.update({"status": "invalid_started_at", "action": "manual_review", "error": str(error)})
                findings.append(finding)
                continue
            freshness = "stale" if age_seconds >= stale_after_seconds else "active"
            finding.update({
                "status": f"pending_{binding_state}_{freshness}",
                "lifecycle_state": "pending",
                "binding_state": binding_state,
                "age_seconds": round(age_seconds, 3),
                "action": "finish_or_abandon" if freshness == "stale" else "none",
            })
            findings.append(finding)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    quarantined = sum(finding.get("action") == "quarantined" for finding in findings)
    needs_attention = any(finding.get("action") not in {"none", "quarantined"} for finding in findings)
    return {
        "schema_version": "1.0",
        "status": "attention_required" if needs_attention else "ok",
        "pending_count": sum(finding.get("lifecycle_state") == "pending" for finding in findings),
        "legacy_quarantined_count": quarantined,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=default_store())
    parser.add_argument("--stale-after-seconds", type=float, default=3600)
    parser.add_argument("--now", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.stale_after_seconds < 0:
        raise SystemExit("stale-after-seconds cannot be negative")
    current_time = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    report = audit(args.store.expanduser(), current_time, args.stale_after_seconds, args.dry_run)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
