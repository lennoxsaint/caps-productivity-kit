from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCRIPT = ROOT / "scripts/routing-receipt.py"
DOCTOR_SCRIPT = ROOT / "scripts/receipt-doctor.py"
RECEIPT_SCHEMA = json.loads((ROOT / "schemas/routing-receipt.schema.json").read_text(encoding="utf-8"))
DIGEST = "sha256:" + "a" * 64


class RoutingReceiptLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Path(self.temporary.name) / "receipts.jsonl"

    def run_receipt(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RECEIPT_SCRIPT), "--store", str(self.store), *arguments],
            check=check,
            capture_output=True,
            text=True,
        )

    def start(self, *, legacy_flags: bool = False) -> str:
        route_flags = (
            ["--model", "gpt-5.6-sol", "--thinking", "medium"]
            if legacy_flags
            else [
                "--requested-model", "gpt-5.6-terra",
                "--requested-thinking", "medium",
                "--resolved-model", "gpt-5.6-sol",
                "--resolved-thinking", "high",
            ]
        )
        result = self.run_receipt(
            "start",
            "--task-class", "coding",
            *route_flags,
            "--worker-kind", "subagent",
            "--route-reason", "bakeoff",
            "--quality-gate-id", "unit-tests",
            "--task-snapshot-complete",
            "--profile-version", "test-v1",
            "--capability-snapshot-digest", DIGEST,
            "--delegation-depth", "1",
        )
        return result.stdout.strip()

    def pending_payload(self, receipt_id: str) -> dict:
        return json.loads((self.store.parent / "pending" / f"{receipt_id}.json").read_text(encoding="utf-8"))

    def recorded_payload(self) -> dict:
        return json.loads(self.store.read_text(encoding="utf-8"))

    def test_start_bind_finish_records_eligible_receipt_without_raw_worker_ref(self):
        receipt_id = self.start()
        started = self.pending_payload(receipt_id)
        self.assertEqual(started["schema_version"], "1.2")
        self.assertEqual(started["lifecycle_state"], "pending")
        self.assertEqual(started["binding_state"], "unbound")
        self.assertEqual(started["requested_model"], "gpt-5.6-terra")
        self.assertEqual(started["resolved_model"], "gpt-5.6-sol")
        self.assertIsNone(started["worker_ref_hash"])

        raw_worker_ref = "worker-secret-reference"
        self.run_receipt("bind", "--receipt-id", receipt_id, "--worker-ref", raw_worker_ref)
        bound = self.pending_payload(receipt_id)
        self.assertEqual(bound["binding_state"], "bound")
        self.assertEqual(
            bound["worker_ref_hash"],
            "sha256:" + hashlib.sha256(raw_worker_ref.encode("utf-8")).hexdigest(),
        )
        self.assertNotIn(raw_worker_ref, json.dumps(bound))

        self.run_receipt(
            "finish",
            "--receipt-id", receipt_id,
            "--outcome", "pass",
            "--delegation-quality", "complete",
            "--capability-verified",
            "--proof-ref", "tests",
        )
        recorded = self.recorded_payload()
        self.assertEqual(recorded["lifecycle_state"], "completed")
        self.assertEqual(recorded["learning_eligibility"], "eligible")
        self.assertTrue(recorded["capability_verified"])
        self.assertFalse((self.store.parent / "pending" / f"{receipt_id}.json").exists())

    def test_complete_verified_failure_remains_learning_eligible(self):
        receipt_id = self.start()
        self.run_receipt("bind", "--receipt-id", receipt_id, "--worker-ref", "worker-1")

        self.run_receipt(
            "finish",
            "--receipt-id", receipt_id,
            "--outcome", "fail",
            "--delegation-quality", "failed",
            "--capability-verified",
            "--severe-error",
            "--retry-count", "1",
            "--rework-seconds", "25",
            "--failure-code", "tests_failed",
        )

        recorded = self.recorded_payload()
        self.assertEqual(recorded["lifecycle_state"], "completed")
        self.assertEqual(recorded["outcome"], "fail")
        self.assertFalse(recorded["quality_passed"])
        self.assertEqual(recorded["delegation_quality"], "failed")
        self.assertEqual(recorded["learning_eligibility"], "eligible")
        self.assertEqual(recorded["rework_seconds"], 25)
        self.assertTrue(recorded["severe_error"])
        self.assertEqual(set(RECEIPT_SCHEMA["required"]) - recorded.keys(), set())
        self.assertIn(recorded["delegation_quality"], RECEIPT_SCHEMA["properties"]["delegation_quality"]["enum"])
        eligible_rule = RECEIPT_SCHEMA["allOf"][-1]["then"]["properties"]
        self.assertNotIn("delegation_quality", eligible_rule)

    def test_legacy_route_flags_fill_requested_and_resolved_fields(self):
        receipt_id = self.start(legacy_flags=True)
        payload = self.pending_payload(receipt_id)
        self.assertEqual(payload["requested_model"], "gpt-5.6-sol")
        self.assertEqual(payload["resolved_model"], "gpt-5.6-sol")
        self.assertEqual(payload["requested_thinking"], "medium")
        self.assertEqual(payload["resolved_thinking"], "medium")

    def test_runtime_supported_dynamic_model_is_recorded_without_a_fixed_enum(self):
        result = self.run_receipt(
            "start",
            "--task-class", "coding",
            "--requested-model", "gpt-next-code",
            "--requested-thinking", "focused",
            "--resolved-model", "gpt-next-code",
            "--resolved-thinking", "focused",
            "--worker-kind", "subagent",
            "--route-reason", "policy",
            "--quality-gate-id", "dynamic-route",
            "--task-snapshot-complete",
            "--profile-version", "test-v1",
            "--capability-snapshot-digest", DIGEST,
            "--delegation-depth", "1",
        )
        payload = self.pending_payload(result.stdout.strip())
        self.assertEqual(payload["requested_model"], "gpt-next-code")
        self.assertEqual(payload["resolved_thinking"], "focused")

    def test_finish_rejects_an_unbound_worker(self):
        receipt_id = self.start()
        result = self.run_receipt(
            "finish",
            "--receipt-id", receipt_id,
            "--outcome", "pass",
            "--delegation-quality", "complete",
            "--capability-verified",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be bound", result.stderr)
        self.assertTrue((self.store.parent / "pending" / f"{receipt_id}.json").exists())
        self.assertFalse(self.store.exists())

    def test_spawn_failure_terminal_closes_unbound_pending_receipt(self):
        receipt_id = self.start()
        self.run_receipt("spawn-failed", "--receipt-id", receipt_id, "--failure-code", "spawn_timeout")
        payload = self.recorded_payload()
        self.assertEqual(payload["lifecycle_state"], "abandoned")
        self.assertEqual(payload["binding_state"], "unbound")
        self.assertEqual(payload["outcome"], "abandoned")
        self.assertEqual(payload["failure_code"], "spawn_timeout")
        self.assertEqual(payload["learning_eligibility"], "ineligible")
        self.assertFalse((self.store.parent / "pending" / f"{receipt_id}.json").exists())

    def test_recording_failure_degrades_observability_without_blocking_finish(self):
        receipt_id = self.start()
        self.run_receipt("bind", "--receipt-id", receipt_id, "--worker-ref", "worker-1")
        self.run_receipt(
            "degrade",
            "--receipt-id", receipt_id,
            "--failure-code", "receipt_recording_interrupted",
        )
        self.run_receipt(
            "finish",
            "--receipt-id", receipt_id,
            "--outcome", "pass",
            "--delegation-quality", "complete",
            "--capability-verified",
        )
        payload = self.recorded_payload()
        self.assertEqual(payload["observability_state"], "degraded")
        self.assertEqual(payload["observability_failure_code"], "receipt_recording_interrupted")
        self.assertEqual(payload["learning_eligibility"], "ineligible")
        self.assertEqual(payload["outcome"], "pass")

    def test_second_bind_cannot_replace_worker_identity(self):
        receipt_id = self.start()
        self.run_receipt("bind", "--receipt-id", receipt_id, "--worker-ref", "worker-1")
        result = self.run_receipt(
            "bind", "--receipt-id", receipt_id, "--worker-ref", "worker-2", check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already bound", result.stderr)

    def test_finish_recovers_without_duplicate_after_append_before_pending_cleanup(self):
        receipt_id = self.start()
        self.run_receipt("bind", "--receipt-id", receipt_id, "--worker-ref", "worker-1")
        pending_path = self.store.parent / "pending" / f"{receipt_id}.json"
        crash_recovery_copy = pending_path.read_text(encoding="utf-8")
        finish_args = (
            "finish", "--receipt-id", receipt_id, "--outcome", "pass",
            "--delegation-quality", "complete", "--capability-verified",
        )
        self.run_receipt(*finish_args)
        pending_path.write_text(crash_recovery_copy, encoding="utf-8")

        result = self.run_receipt(*finish_args)

        self.assertEqual(json.loads(result.stdout)["status"], "already_recorded")
        self.assertEqual(len(self.store.read_text(encoding="utf-8").splitlines()), 1)
        self.assertFalse(pending_path.exists())


class ReceiptDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Path(self.temporary.name) / "receipts.jsonl"
        self.pending = self.store.parent / "pending"
        self.pending.mkdir()

    def run_doctor(self, *arguments: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--store", str(self.store), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_doctor_quarantines_unresolved_legacy_without_inventing_outcome(self):
        legacy = {
            "schema_version": "1.1",
            "receipt_id": "00000000-0000-4000-8000-000000000001",
            "started_at": "2026-08-01T00:00:00+00:00",
            "task_class": "coding",
            "model": "gpt-5.6-sol",
            "thinking": "medium",
        }
        source = self.pending / f"{legacy['receipt_id']}.json"
        original = json.dumps(legacy, sort_keys=True) + "\n"
        source.write_text(original, encoding="utf-8")

        report = self.run_doctor()

        target = self.store.parent / "quarantine" / "legacy_pending_unresolved" / source.name
        self.assertFalse(source.exists())
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertFalse(self.store.exists())
        self.assertEqual(report["findings"][0]["status"], "legacy_pending_unresolved")
        self.assertNotIn("outcome", report["findings"][0])

    def test_doctor_reports_current_pending_without_closing_it(self):
        current = {
            "schema_version": "1.2",
            "receipt_id": "00000000-0000-4000-8000-000000000002",
            "started_at": "2026-08-16T00:00:00+00:00",
            "lifecycle_state": "pending",
            "binding_state": "bound",
        }
        source = self.pending / f"{current['receipt_id']}.json"
        original = json.dumps(current, sort_keys=True) + "\n"
        source.write_text(original, encoding="utf-8")

        report = self.run_doctor("--now", "2026-08-16T00:05:00+00:00", "--stale-after-seconds", "60")

        self.assertTrue(source.exists())
        self.assertEqual(source.read_text(encoding="utf-8"), original)
        self.assertEqual(report["findings"][0]["status"], "pending_bound_stale")
        self.assertFalse(self.store.exists())

    def test_doctor_dry_run_does_not_move_legacy_pending(self):
        source = self.pending / "legacy.json"
        source.write_text('{"schema_version":"1.1"}\n', encoding="utf-8")

        report = self.run_doctor("--dry-run")

        self.assertTrue(source.exists())
        self.assertEqual(report["findings"][0]["action"], "would_quarantine")


if __name__ == "__main__":
    unittest.main()
