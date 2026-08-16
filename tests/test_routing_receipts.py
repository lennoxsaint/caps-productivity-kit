from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluate_receipts", ROOT / "scripts/evaluate-routing-receipts.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def receipt(
    model: str,
    thinking: str,
    elapsed: float,
    passed: bool = True,
    *,
    eligible: bool = True,
    capability_verified: bool = True,
) -> dict:
    return {
        "schema_version": "1.2",
        "task_class": "coding",
        "requested_model": model,
        "requested_thinking": thinking,
        "resolved_model": model,
        "resolved_thinking": thinking,
        "elapsed_seconds": elapsed,
        "rework_seconds": 0,
        "quality_passed": passed,
        "outcome": "pass" if passed else "fail",
        "severe_error": False,
        "task_snapshot_complete": True,
        "delegation_quality": "complete",
        "lifecycle_state": "completed",
        "binding_state": "bound",
        "capability_verified": capability_verified,
        "observability_state": "complete",
        "learning_eligibility": "eligible" if eligible else "ineligible",
    }


class RoutingReceiptTests(unittest.TestCase):
    def test_balanced_terra_win_can_promote(self):
        values = []
        for _ in range(10):
            values.extend([
                receipt("gpt-5.6-luna", "high", 20),
                receipt("gpt-5.6-terra", "high", 10),
                receipt("gpt-5.6-sol", "medium", 15),
            ])
        evaluation = MODULE.evaluate(values, 30, 5, 0.10)
        result = evaluation["task_classes"]["coding"]["recommendation"]
        self.assertTrue(result["promoted"])
        self.assertEqual(result["model"], "gpt-5.6-terra")
        self.assertEqual(evaluation["qualified_receipt_count"], 30)

    def test_quality_failure_and_rework_are_counted_for_eligible_receipts(self):
        values = []
        for index in range(10):
            terra = receipt("gpt-5.6-terra", "high", 10, passed=index != 0)
            if index == 0:
                terra["rework_seconds"] = 25
            values.extend([
                receipt("gpt-5.6-luna", "high", 20),
                terra,
                receipt("gpt-5.6-sol", "medium", 15),
            ])
        task_class = MODULE.evaluate(values, 30, 5, 0.10)["task_classes"]["coding"]
        terra = task_class["candidates"]["gpt-5.6-terra/high"]
        self.assertEqual(terra["failures"], 1)
        self.assertEqual(terra["rework_seconds"], 25)
        self.assertEqual(terra["elapsed_seconds"], 125)
        self.assertNotEqual(task_class["recommendation"]["model"], "gpt-5.6-terra")

    def test_complete_verified_failure_counts_even_with_legacy_ineligible_label(self):
        failed = receipt("gpt-5.6-terra", "high", 10, passed=False, eligible=False)
        failed["delegation_quality"] = "failed"
        failed["severe_error"] = True
        failed["rework_seconds"] = 25

        evaluation = MODULE.evaluate([failed], 1, 1, 0)
        candidate = evaluation["task_classes"]["coding"]["candidates"]["gpt-5.6-terra/high"]

        self.assertEqual(evaluation["qualified_receipt_count"], 1)
        self.assertEqual(evaluation["excluded_receipt_count"], 0)
        self.assertEqual(candidate["failures"], 1)
        self.assertEqual(candidate["severe_errors"], 1)
        self.assertEqual(candidate["rework_seconds"], 25)
        self.assertEqual(candidate["weak_delegations"], 1)

    def test_incomplete_snapshot_is_excluded_from_learning(self):
        incomplete = receipt("gpt-5.6-terra", "high", 10)
        incomplete["task_snapshot_complete"] = False

        evaluation = MODULE.evaluate([incomplete], 1, 1, 0)

        self.assertEqual(evaluation["qualified_receipt_count"], 0)
        self.assertEqual(evaluation["excluded_receipt_count"], 1)
        self.assertEqual(evaluation["exclusion_reasons"], {"task_snapshot_incomplete": 1})

    def test_incomplete_conductor_snapshot_disqualifies_candidate(self):
        values = []
        for index in range(10):
            luna = receipt("gpt-5.6-luna", "high", 20)
            terra = receipt("gpt-5.6-terra", "high", 10)
            sol = receipt("gpt-5.6-sol", "medium", 15)
            if index == 0:
                terra["task_snapshot_complete"] = False
            values.extend([luna, terra, sol])
        result = MODULE.evaluate(values, 30, 5, 0.10)["task_classes"]["coding"]["recommendation"]
        self.assertNotEqual(result["model"], "gpt-5.6-terra")

    def test_partial_delegation_disqualifies_candidate(self):
        values = []
        for index in range(10):
            luna = receipt("gpt-5.6-luna", "high", 20)
            terra = receipt("gpt-5.6-terra", "high", 10)
            sol = receipt("gpt-5.6-sol", "medium", 15)
            if index == 0:
                terra["delegation_quality"] = "partial"
            values.extend([luna, terra, sol])
        result = MODULE.evaluate(values, 30, 5, 0.10)["task_classes"]["coding"]["recommendation"]
        self.assertNotEqual(result["model"], "gpt-5.6-terra")

    def test_only_complete_capability_verified_observable_receipts_qualify(self):
        values = [
            receipt("gpt-5.6-sol", "medium", 10),
            receipt("gpt-5.6-sol", "medium", 11, eligible=False),
            receipt("gpt-5.6-sol", "medium", 12, capability_verified=False),
            {
                "schema_version": "1.1",
                "task_class": "coding",
                "model": "gpt-5.6-sol",
                "thinking": "medium",
                "elapsed_seconds": 13,
                "rework_seconds": 0,
                "quality_passed": True,
                "severe_error": False,
                "task_snapshot_complete": True,
                "delegation_quality": "complete",
            },
        ]
        values[1]["observability_state"] = "degraded"

        evaluation = MODULE.evaluate(values, 1, 1, 0)

        self.assertEqual(evaluation["receipt_count"], 4)
        self.assertEqual(evaluation["qualified_receipt_count"], 1)
        self.assertEqual(evaluation["excluded_receipt_count"], 3)
        self.assertEqual(
            evaluation["exclusion_reasons"],
            {"capability_not_verified": 1, "legacy_capability_unverified": 1, "observability_degraded": 1},
        )


if __name__ == "__main__":
    unittest.main()
