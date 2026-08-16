from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_install_records_version_and_preserves_local_title_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            first = subprocess.run(
                [str(ROOT / "install.sh"), str(project), "--no-open", "--no-agents-update"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            preferences = project / ".caps/config/title-preferences.json"
            preferences.write_text('{"enabled": false, "owner": "local"}\n', encoding="utf-8")
            second = subprocess.run(
                [str(ROOT / "install.sh"), str(project), "--no-open", "--no-agents-update"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                json.loads(preferences.read_text(encoding="utf-8")),
                {"enabled": False, "owner": "local"},
            )
            manifest = json.loads(
                (project / ".caps/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], "0.4.0")
            self.assertIn("automations/pinned-title-sync/automation.toml", manifest["managed_files"])
            self.assertIn("scripts/automation-doctor.py", manifest["managed_files"])
            self.assertIn("scripts/pinned-thread-snapshot.py", manifest["managed_files"])
            self.assertIn(
                "scripts/installed-tests/test_installed_commands.py",
                manifest["managed_files"],
            )
            self.assertNotIn("config/title-preferences.json", manifest["managed_files"])
            self.assertTrue((project / ".caps/defaults/title-preferences.json").exists())
            doctor = subprocess.run(
                [
                    "python3",
                    str(project / ".caps/scripts/automation-doctor.py"),
                    "--project",
                    str(project),
                    "activation",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertIn(str(project.resolve()), doctor.stdout)


if __name__ == "__main__":
    unittest.main()
