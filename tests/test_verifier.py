from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstalledVerifierTests(unittest.TestCase):
    def install_project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir()
        result = subprocess.run(
            [str(ROOT / "install.sh"), str(project), "--no-open", "--no-agents-update"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return project

    def run_installed_verifier(self, project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(project / ".caps/scripts/verify.sh")],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_installed_layout_verifies_without_source_only_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            caps = project / ".caps"

            for source_only in ("README.md", "AGENTS.md", "install.sh", "packs", "channels"):
                self.assertFalse((caps / source_only).exists())

            result = self.run_installed_verifier(project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CAPS installed layout verification passed.", result.stdout)

    def test_installed_layout_rejects_an_undeclared_managed_file_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            changed = project / ".caps/docs/updates.md"
            changed.write_text(changed.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

            result = self.run_installed_verifier(project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Managed file hash mismatch: docs/updates.md", result.stderr)

    def test_installed_layout_accepts_a_declared_local_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            caps = project / ".caps"
            changed = caps / "docs/updates.md"
            changed.write_text(changed.read_text(encoding="utf-8") + "\nlocal notes\n", encoding="utf-8")
            manifest_path = caps / "install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["local_overrides"] = ["docs/updates.md"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_installed_verifier(project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Declared local override: docs/updates.md", result.stdout)

    def test_installed_layout_rejects_an_unknown_local_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            manifest_path = project / ".caps/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["local_overrides"] = ["docs/not-managed.md"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_installed_verifier(project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid local override: docs/not-managed.md", result.stderr)

    def test_installed_layout_requires_mapped_files_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            manifest_path = project / ".caps/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["managed_files"].pop("docs/updates.md")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_installed_verifier(project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Required installed file is not managed: docs/updates.md",
                result.stderr,
            )

    def test_installed_layout_requires_every_contract_file_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.install_project(Path(temporary))
            manifest_path = project / ".caps/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["managed_files"].pop("docs/dynamic-harnesses.md")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            result = self.run_installed_verifier(project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Required installed file is not managed: docs/dynamic-harnesses.md",
                result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
