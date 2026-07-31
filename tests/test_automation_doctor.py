from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "automation_doctor",
    ROOT / "scripts/automation-doctor.py",
)
DOCTOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(DOCTOR)


class AutomationDoctorTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "project"
        automations = project / ".caps/automations"
        shutil.copytree(ROOT / "automations", automations)
        return project

    def write_native(self, native_root: Path, project: Path, automation_id: str) -> None:
        project = project.resolve()
        spec = DOCTOR.AUTOMATIONS[automation_id]
        destination = native_root / automation_id / "automation.toml"
        destination.parent.mkdir(parents=True)
        prompt_path = project / ".caps/automations" / spec["directory"] / "prompt.md"
        destination.write_text(
            "\n".join(
                [
                    "version = 1",
                    f'id = "{automation_id}"',
                    f'kind = "{spec["kind"]}"',
                    f'name = "{spec["name"]}"',
                    f'prompt = "Read {prompt_path} and execute it exactly."',
                    'status = "ACTIVE"',
                    f'rrule = "{spec["rrule"]}"',
                    f'model = "{spec["model"]}"',
                    f'reasoning_effort = "{spec["reasoning_effort"]}"',
                    'execution_environment = "local"',
                    'target = { type = "project", project_id = "test-project" }',
                    f'cwds = ["{project}"]',
                    "created_at = 1",
                    "updated_at = 2",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_missing_native_registration_is_reported_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            native_root = root / "native"

            report = DOCTOR.inspect_automations(project, native_root)

            self.assertEqual(report["status"], "registration_required")
            self.assertEqual(
                {item["native_status"] for item in report["automations"]},
                {"missing"},
            )
            self.assertFalse(native_root.exists())

    def test_matching_native_registrations_are_active(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            native_root = root / "native"
            for automation_id in DOCTOR.AUTOMATIONS:
                self.write_native(native_root, project, automation_id)

            report = DOCTOR.inspect_automations(project, native_root)

            self.assertEqual(report["status"], "active")
            self.assertTrue(all(item["native_status"] == "active" for item in report["automations"]))

    def test_native_cwd_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root)
            native_root = root / "native"
            for automation_id in DOCTOR.AUTOMATIONS:
                self.write_native(native_root, project, automation_id)
            title_path = native_root / "caps-pinned-title-sync/automation.toml"
            title_path.write_text(
                title_path.read_text(encoding="utf-8").replace(
                    f'cwds = ["{project.resolve()}"]',
                    'cwds = ["/wrong/project"]',
                ),
                encoding="utf-8",
            )

            report = DOCTOR.inspect_automations(project, native_root)

            self.assertEqual(report["status"], "drift")
            title = next(
                item for item in report["automations"]
                if item["id"] == "caps-pinned-title-sync"
            )
            self.assertIn("cwd", title["mismatches"])

    def test_activation_prompt_uses_absolute_paths_and_native_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))

            prompt = DOCTOR.activation_prompt(project)

            self.assertIn(str(project.resolve()), prompt)
            self.assertIn("native Scheduled task controls", prompt)
            self.assertIn("Never edit Codex registry files", prompt)
            self.assertIn("FREQ=MINUTELY;INTERVAL=20", prompt)
            self.assertIn("FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0", prompt)
            self.assertIn("gpt-5.6-luna", prompt)
            self.assertIn("read back", prompt.lower())


if __name__ == "__main__":
    unittest.main()
