from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/model-bakeoff.py"
FIXTURES = ROOT / "tests/fixtures/bakeoff"
SPEC = importlib.util.spec_from_file_location("model_bakeoff", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class ModelBakeoffTests(unittest.TestCase):
    def test_public_task_manifest_is_frozen(self):
        manifest = MODULE.task_manifest()
        self.assertEqual(manifest["bakeoff_version"], "0.4.0")
        self.assertEqual(
            [task["task_class"] for task in manifest["tasks"]],
            ["transformation", "coding", "proof_review"],
        )
        self.assertEqual(
            manifest["tasks_digest"],
            "72fda157d05c6187d059a1542e5d5c72f56a824fc1461aa5589ceeddb2eeac98",
        )
        self.assertTrue(all(task["public_safe"] for task in manifest["tasks"]))

    def test_valid_fixture_uses_speed_only_after_mandatory_correctness(self):
        output = MODULE.evaluate(load_fixture("valid-results.json"))
        recommendations = {
            item["task_class"]: item for item in output["profile"]["recommendations"]
        }

        self.assertEqual(recommendations["transformation"]["model"], "gpt-5.6-terra")
        self.assertEqual(recommendations["transformation"]["selection_basis"], "performance_lead")
        self.assertEqual(recommendations["coding"]["model"], "gpt-5.6-luna")
        self.assertEqual(recommendations["coding"]["selection_basis"], "least_expensive_passing")
        self.assertEqual(recommendations["proof_review"]["model"], "gpt-5.6-terra")
        self.assertIn("gpt-5.6-luna", recommendations["proof_review"]["excluded_unsupported_models"])
        self.assertIn("gpt-5.6-sol", recommendations["proof_review"]["excluded_failed_models"])

        self.assertEqual(output["profile"]["ttl_days"], 30)
        self.assertEqual(output["profile"]["valid_until"], "2026-09-15T00:00:00+00:00")
        self.assertEqual(output["profile"]["visibility"], "private")
        self.assertEqual(
            output["public_fallback"]["coding"],
            {"model": "gpt-5.6-sol", "thinking": "medium"},
        )

    def test_valid_results_preserve_only_redacted_traceability_bindings(self):
        payload = load_fixture("valid-results.json")
        output = MODULE.evaluate(payload)
        traceability = output["traceability"]

        self.assertEqual(traceability["tasks_digest"], MODULE.task_manifest()["tasks_digest"])
        self.assertEqual(
            traceability["capability_snapshot_digest"],
            "sha256:4537fe3ad9976783e7198f8ea96f3d1475778f051444e238cbe9d7dab4e8937a",
        )
        self.assertEqual(len(traceability["result_bindings"]), 9)
        self.assertEqual(
            {binding["receipt_ref_hash"] for binding in traceability["result_bindings"]},
            {record["receipt_ref_hash"] for record in payload["results"]},
        )
        self.assertTrue(
            all(
                set(binding) == {"task_id", "model", "receipt_ref_hash"}
                for binding in traceability["result_bindings"]
            )
        )
        serialized = json.dumps(output)
        self.assertNotIn("receipt_ref\"", serialized)
        self.assertNotIn("capability_source", serialized)

    def test_rejects_result_not_bound_to_frozen_tasks_or_common_capability_snapshot(self):
        payload = load_fixture("valid-results.json")
        payload["results"][0]["tasks_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "tasks_digest must match the frozen task manifest"):
            MODULE.evaluate(payload)

        payload = load_fixture("valid-results.json")
        payload["results"][0]["capability_snapshot_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "same capability_snapshot_digest"):
            MODULE.evaluate(payload)

    def test_rejects_raw_malformed_or_reused_receipt_references(self):
        payload = load_fixture("valid-results.json")
        payload["results"][0]["receipt_ref_hash"] = "private/receipt.json"
        with self.assertRaisesRegex(ValueError, "receipt_ref_hash must be sha256"):
            MODULE.evaluate(payload)

        payload = load_fixture("valid-results.json")
        payload["results"][1]["receipt_ref_hash"] = payload["results"][0]["receipt_ref_hash"]
        with self.assertRaisesRegex(ValueError, "unique receipt_ref_hash"):
            MODULE.evaluate(payload)

    def test_one_failed_gate_disqualifies_fastest_route(self):
        payload = load_fixture("valid-results.json")
        terra = next(
            item
            for item in payload["results"]
            if item["task_id"] == "bounded-coding-v1" and item["model"] == "gpt-5.6-terra"
        )
        terra["elapsed_seconds"] = 1
        terra["gates"]["targeted_tests_passed"] = False
        output = MODULE.evaluate(payload)
        recommendation = next(
            item for item in output["profile"]["recommendations"] if item["task_class"] == "coding"
        )
        self.assertNotEqual(recommendation["model"], "gpt-5.6-terra")
        self.assertIn("gpt-5.6-terra", recommendation["excluded_failed_models"])

    def test_exact_ten_percent_performance_lead_wins(self):
        payload = load_fixture("valid-results.json")
        coding = {
            item["model"]: item
            for item in payload["results"]
            if item["task_id"] == "bounded-coding-v1"
        }
        coding["gpt-5.6-sol"]["elapsed_seconds"] = 10
        coding["gpt-5.6-terra"]["elapsed_seconds"] = 11
        coding["gpt-5.6-luna"]["elapsed_seconds"] = 20
        output = MODULE.evaluate(payload)
        recommendation = next(
            item for item in output["profile"]["recommendations"] if item["task_class"] == "coding"
        )
        self.assertEqual(recommendation["model"], "gpt-5.6-sol")
        self.assertEqual(recommendation["performance_lead"], 0.1)

    def test_rejects_missing_duplicate_or_unknown_task_model_pairs(self):
        payload = load_fixture("valid-results.json")
        payload["results"][-1] = copy.deepcopy(payload["results"][0])
        with self.assertRaisesRegex(ValueError, "exactly one result for every task/model pair"):
            MODULE.evaluate(payload)

    def test_rejects_unverified_capability_and_non_read_only_execution(self):
        payload = load_fixture("valid-results.json")
        payload["results"][0]["capability_source"] = ""
        with self.assertRaisesRegex(ValueError, "capability_source"):
            MODULE.evaluate(payload)

        payload = load_fixture("valid-results.json")
        payload["results"][0]["read_only"] = False
        with self.assertRaisesRegex(ValueError, "read_only must be true"):
            MODULE.evaluate(payload)

    def test_rejects_unknown_or_missing_gate_fields(self):
        payload = load_fixture("valid-results.json")
        payload["results"][0]["gates"]["invented_gate"] = True
        with self.assertRaisesRegex(ValueError, "gates must exactly match"):
            MODULE.evaluate(payload)

    def test_cli_is_deterministic_and_never_runs_a_model(self):
        command = [sys.executable, str(SCRIPT), "--results", str(FIXTURES / "valid-results.json")]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(json.loads(first.stdout)["execution_mode"], "evaluate_supplied_results_only")


if __name__ == "__main__":
    unittest.main()
