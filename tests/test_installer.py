from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - supported on Python 3.10.
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def run_install(self, project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(ROOT / "install.sh"),
                str(project),
                "--no-open",
                "--no-agents-update",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_fresh_install_creates_supported_codex_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            result = self.run_install(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = project / ".codex/config.toml"
            self.assertTrue(config.is_file())
            data = tomllib.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "gpt-6-astra")
            self.assertEqual(data["model_reasoning_effort"], "low")
            self.assertEqual(data["agents"]["enabled"], True)
            self.assertEqual(data["agents"]["default_subagent_model"], "gpt-5.6-luna")
            self.assertEqual(data["agents"]["default_subagent_reasoning_effort"], "max")
            self.assertEqual(data["agents"]["max_concurrent_threads_per_session"], 6)
            self.assertNotIn("service_tier", data)

    def test_upgrade_preserves_existing_codex_config_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            first = self.run_install(project)
            self.assertEqual(first.returncode, 0, first.stderr)
            config = project / ".codex/config.toml"
            owner_config = (
                b"# owner formatting and comments stay intact\n"
                b"model = \"gpt-5.6-sol\" # owner-selected\n"
                b"model_reasoning_effort = \"xhigh\"\n\n"
                b"[agents]\n"
                b"enabled = false\n"
                b"custom_setting = \"preserve\"\n"
            )
            config.write_bytes(owner_config)
            second = self.run_install(project)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(config.read_bytes(), owner_config)
            self.assertIn("Validated existing Codex config", second.stdout)

    def test_malformed_codex_config_fails_before_install_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            config = project / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            malformed = b"model = [\n"
            config.write_bytes(malformed)
            result = self.run_install(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_toml", result.stderr)
            self.assertEqual(config.read_bytes(), malformed)
            self.assertFalse((project / ".caps").exists())
            self.assertFalse((project / "AGENTS.md").exists())

    def test_global_codex_directory_never_creates_nested_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            codex_directory = Path(temporary) / '.codex'
            codex_directory.mkdir()
            original = b'model = "gpt-5.6-sol"\nmodel_reasoning_effort = "xhigh"\n'
            (codex_directory / 'config.toml').write_bytes(original)
            result = self.run_install(codex_directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((codex_directory / 'config.toml').read_bytes(), original)
            self.assertFalse((codex_directory / '.codex').exists())

    def test_upgrade_preserves_modified_managed_docs(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self.run_install(project).returncode, 0)
            document = project / '.caps/docs/conductor-workflow.md'
            owned = document.read_bytes() + b'\nOwner policy must survive.\n'
            document.write_bytes(owned)
            self.assertEqual(self.run_install(project).returncode, 0)
            self.assertEqual(document.read_bytes(), owned)
            manifest = json.loads((project / '.caps/install-manifest.json').read_text())
            self.assertIn('docs/conductor-workflow.md', manifest['local_overrides'])

    def test_install_records_version_and_preserves_local_title_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            first = self.run_install(project)
            self.assertEqual(first.returncode, 0, first.stderr)
            preferences = project / ".caps/config/title-preferences.json"
            preferences.write_text('{"enabled": false, "owner": "local"}\n', encoding="utf-8")
            second = self.run_install(project)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                json.loads(preferences.read_text(encoding="utf-8")),
                {"enabled": False, "owner": "local"},
            )
            manifest = json.loads(
                (project / ".caps/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text().strip())
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
