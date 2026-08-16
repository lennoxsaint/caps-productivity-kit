from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class InstalledCommandTests(unittest.TestCase):
    def test_routing_examples_validate(self):
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/verify-routing.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_automation_activation_uses_the_installed_project(self):
        project = ROOT.parent
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/automation-doctor.py"),
                "--project",
                str(project),
                "activation",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(project.resolve()), result.stdout)

    def test_routing_receipt_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "receipts.jsonl"
            started = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/routing-receipt.py"),
                    "--store",
                    str(store),
                    "start",
                    "--task-class",
                    "coding",
                    "--model",
                    "gpt-5.6-sol",
                    "--thinking",
                    "medium",
                    "--route-reason",
                    "policy",
                    "--quality-gate-id",
                    "installed-tests",
                    "--task-snapshot-complete",
                    "--profile-version",
                    "installed-test",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            receipt_id = started.stdout.strip()
            finished = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/routing-receipt.py"),
                    "--store",
                    str(store),
                    "finish",
                    "--receipt-id",
                    receipt_id,
                    "--outcome",
                    "pass",
                    "--delegation-quality",
                    "complete",
                    "--proof-ref",
                    "installed-tests",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(finished.returncode, 0, finished.stderr)
            receipt = json.loads(store.read_text(encoding="utf-8"))
            self.assertTrue(receipt["quality_passed"])


if __name__ == "__main__":
    unittest.main()
