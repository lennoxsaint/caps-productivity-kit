from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluate_receipts", ROOT / "scripts/evaluate-routing-receipts.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def receipt(model: str, thinking: str, elapsed: float, passed: bool = True) -> dict:
    return {
        "task_class": "coding",
        "model": model,
        "thinking": thinking,
        "elapsed_seconds": elapsed,
        "rework_seconds": 0,
        "quality_passed": passed,
        "severe_error": False,
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
        result = MODULE.evaluate(values, 30, 5, 0.10)["task_classes"]["coding"]["recommendation"]
        self.assertTrue(result["promoted"])
        self.assertEqual(result["model"], "gpt-5.6-terra")

    def test_quality_failure_disqualifies_candidate(self):
        values = []
        for index in range(10):
            values.extend([
                receipt("gpt-5.6-luna", "high", 20),
                receipt("gpt-5.6-terra", "high", 10, passed=index != 0),
                receipt("gpt-5.6-sol", "medium", 15),
            ])
        result = MODULE.evaluate(values, 30, 5, 0.10)["task_classes"]["coding"]["recommendation"]
        self.assertNotEqual(result["model"], "gpt-5.6-terra")


if __name__ == "__main__":
    unittest.main()
