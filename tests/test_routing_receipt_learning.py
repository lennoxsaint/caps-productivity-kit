from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCRIPT = ROOT / "scripts/routing-receipt.py"
EVALUATOR_SPEC = importlib.util.spec_from_file_location(
    "evaluate_routing_receipts", ROOT / "scripts/evaluate-routing-receipts.py"
)
EVALUATOR = importlib.util.module_from_spec(EVALUATOR_SPEC)
assert EVALUATOR_SPEC.loader
EVALUATOR_SPEC.loader.exec_module(EVALUATOR)

DIGEST = "sha256:" + "a" * 64


def current_receipt(
    *,
    receipt_id: str = "00000000-0000-4000-8000-000000000001",
    model: str = "gpt-5.6-luna",
    thinking: str = "max",
    passed: bool = True,
    checks: bool | None = True,
    lead_reviewed: bool | None = True,
    usage: float | None = None,
) -> dict:
    return {
        "schema_version": "1.2",
        "event_type": "receipt",
        "receipt_id": receipt_id,
        "finished_at": "2026-09-09T00:00:00+00:00",
        "lifecycle_state": "completed",
        "binding_state": "bound",
        "capability_verified": True,
        "observability_state": "complete",
        "task_snapshot_complete": True,
        "task_class": "coding",
        "resolved_model": model,
        "resolved_thinking": thinking,
        "quality_passed": passed,
        "gate_result": "pass" if passed else "fail",
        "outcome": "pass" if passed else "fail",
        "severe_error": False,
        "delegation_quality": "complete",
        "elapsed_seconds": 10,
        "rework_seconds": 0,
        "retry_count": 0,
        "attempts": 1,
        "lead_reviewed": lead_reviewed,
        "task_checks": [{"label": "tests", "passed": checks}] if checks is not None else [],
        "task_checks_passed": checks,
        "subscription_usage": usage,
        "correction_count": 0,
        "owner_correction_count": 0,
    }


class ReceiptLearningTests(unittest.TestCase):
    def run_receipt(self, store: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RECEIPT_SCRIPT), "--store", str(store), *arguments],
            check=check,
            capture_output=True,
            text=True,
        )

    def start_and_bind(self, store: Path) -> str:
        started = self.run_receipt(
            store,
            "start",
            "--task-class", "coding",
            "--model", "gpt-5.6-luna",
            "--thinking", "max",
            "--route-reason", "policy",
            "--quality-gate-id", "tests",
            "--task-snapshot-complete",
            "--profile-version", "test-v1",
            "--capability-snapshot-digest", DIGEST,
        )
        receipt_id = started.stdout.strip()
        self.run_receipt(store, "bind", "--receipt-id", receipt_id, "--worker-ref", "worker-1")
        return receipt_id

    def finish_args(self, receipt_id: str, *extra: str) -> tuple[str, ...]:
        return (
            "finish", "--receipt-id", receipt_id, "--outcome", "pass",
            "--delegation-quality", "complete", "--capability-verified", *extra,
        )

    def test_passing_acceptance_needs_checks_and_independent_lead_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "receipts.jsonl"
            receipt_id = self.start_and_bind(store)

            missing_check = self.run_receipt(
                store, *self.finish_args(receipt_id, "--lead-reviewed"), check=False
            )
            self.assertNotEqual(missing_check.returncode, 0)
            self.assertIn("task-specific checks", missing_check.stderr)

            failed_check = self.run_receipt(
                store,
                *self.finish_args(receipt_id, "--lead-reviewed", "--task-check", "tests=fail"),
                check=False,
            )
            self.assertNotEqual(failed_check.returncode, 0)
            self.assertIn("task-specific checks", failed_check.stderr)

            self.run_receipt(
                store,
                *self.finish_args(receipt_id, "--lead-reviewed", "--task-check", "tests=pass"),
            )
            row = json.loads(store.read_text(encoding="utf-8"))
            self.assertTrue(row["lead_reviewed"])
            self.assertTrue(row["task_checks_passed"])

    def test_failed_checks_cannot_be_counted_as_accepted(self):
        item = current_receipt(checks=False)
        result = EVALUATOR.evaluate([item], 1, 1, 0)
        candidate = result["task_classes"]["coding"]["candidates"]["gpt-5.6-luna/max"]
        self.assertEqual(candidate["accepted_outcomes"], 0)
        self.assertEqual(candidate["failed_checks"], 1)

    def test_contradictory_check_summary_cannot_override_failed_detail(self):
        item = current_receipt(checks=True)
        item["task_checks"] = [{"label": "tests", "passed": False}]
        result = EVALUATOR.evaluate([item], 1, 1, 0)
        candidate = result["task_classes"]["coding"]["candidates"]["gpt-5.6-luna/max"]
        self.assertEqual(candidate["accepted_outcomes"], 0)
        self.assertEqual(candidate["failed_checks"], 1)

    def test_legacy_missing_review_marker_stays_unknown_but_remains_readable(self):
        legacy = current_receipt()
        legacy.pop("event_type")
        legacy.pop("lead_reviewed")
        legacy.pop("task_checks")
        legacy.pop("task_checks_passed")
        result = EVALUATOR.score([legacy])
        self.assertEqual(result["legacy_receipts"], 1)
        self.assertEqual(result["lead_review_legacy"], 1)
        self.assertEqual(result["accepted_outcomes"], 0)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["unknown_acceptance"], 1)

    def test_unknown_usage_is_not_converted_to_zero_or_derived_from_tokens(self):
        item = current_receipt(usage=None)
        item["input_tokens"] = 1000
        item["output_tokens"] = 2000
        item["estimated_cost_usd"] = 0.01
        effective = EVALUATOR.effective_item(item)
        result = EVALUATOR.score([effective])
        self.assertIsNone(result["subscription_usage_total"])
        self.assertIsNone(result["accepted_outcomes_per_subscription_usage"])

    def test_owner_correction_is_append_only_idempotent_and_counts_rework(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "receipts.jsonl"
            receipt_id = self.start_and_bind(store)
            self.run_receipt(
                store,
                *self.finish_args(
                    receipt_id,
                    "--lead-reviewed", "--task-check", "tests=pass",
                    "--subscription-usage", "2", "--subscription-usage-source", "provider",
                ),
            )
            original = store.read_text(encoding="utf-8").splitlines()[0]

            correction = self.run_receipt(
                store,
                "correct", "--receipt-id", receipt_id,
                "--idempotency-key", "owner-correction-1",
                "--not-accepted", "--rework-seconds", "3", "--reason", "owner-finding",
            )
            self.assertEqual(json.loads(correction.stdout)["status"], "recorded")
            repeated = self.run_receipt(
                store,
                "correction", "--receipt-id", receipt_id,
                "--idempotency-key", "owner-correction-1",
                "--not-accepted", "--rework-seconds", "3", "--reason", "owner-finding",
            )
            self.assertEqual(json.loads(repeated.stdout)["status"], "already_recorded")
            rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], json.loads(original))
            self.assertEqual(rows[1]["receipt_id"], receipt_id)
            self.assertEqual(rows[1]["event_type"], "correction")

            result = EVALUATOR.evaluate(rows, 1, 1, 0)
            candidate = result["task_classes"]["coding"]["candidates"]["gpt-5.6-luna/max"]
            self.assertEqual(candidate["accepted_outcomes"], 0)
            self.assertEqual(candidate["corrected_receipts"], 1)
            self.assertEqual(candidate["rework_seconds"], 3)
            self.assertEqual(result["correction_event_count"], 1)
            self.assertTrue(rows[1]["accepted_before"])

    def test_recent_correction_keeps_older_base_in_read_window(self):
        now = datetime.now(timezone.utc)
        base = current_receipt()
        base["finished_at"] = (now - timedelta(days=8)).isoformat()
        correction = {
            "schema_version": "1.2",
            "event_type": "correction",
            "receipt_id": base["receipt_id"],
            "correction_id": "late-finding",
            "idempotency_key_hash": "sha256:" + "b" * 64,
            "corrected_at": now.isoformat(),
            "owner_correction": True,
            "accepted_before": True,
            "accepted_after": False,
            "rework_seconds": 4,
            "attempts_added": 1,
            "evidence_kind": "owner_correction",
        }
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "receipts.jsonl"
            store.write_text(
                "\n".join(json.dumps(row) for row in (base, correction)) + "\n",
                encoding="utf-8",
            )
            entries = EVALUATOR.load_entries(store, 7)
            self.assertEqual(len(entries), 2)
            result = EVALUATOR.evaluate(entries, 1, 1, 0)
            candidate = result["task_classes"]["coding"]["candidates"]["gpt-5.6-luna/max"]
            self.assertEqual(candidate["rework_seconds"], 4)
            self.assertEqual(candidate["accepted_outcomes"], 0)

    def test_weekly_summary_is_bounded_and_recommendation_only(self):
        item = current_receipt(usage=None)
        summary = EVALUATOR.weekly_summary([item], days=7)
        serialized = json.dumps(summary)
        self.assertTrue(summary["recommendation_only"])
        self.assertEqual(summary["window_days"], 7)
        self.assertIsNone(summary["evidence"]["subscription_usage_total"])
        self.assertIn("observational", serialized)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("raw prompt", serialized)


if __name__ == "__main__":
    unittest.main()
