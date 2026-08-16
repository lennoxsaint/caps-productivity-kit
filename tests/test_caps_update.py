from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("caps_update", ROOT / "scripts/caps-update.py")
UPDATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(UPDATE)
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_release",
    ROOT / "scripts/build-release.py",
)
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
assert BUILD_SPEC.loader
BUILD_SPEC.loader.exec_module(BUILD)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def release_archive(version: str = "0.3.2") -> bytes:
    files = {
        "automations/example.toml": b"status = \"PAUSED\"\n",
        "docs/example.md": b"new docs\n",
        "examples/example.md": b"example\n",
        "prompts/example.md": b"prompt\n",
        "prompts/bootstrap-caps-conductor.md": b"bootstrap\n",
        "schemas/example.json": b"{}\n",
        "scripts/example.py": b"print('ok')\n",
        "templates/example.md": b"template\n",
        "scripts/install-contract.json": b'{"schema_version":"1.0","source_mappings":{"scripts":"scripts"},"required_unmanaged_files":[],"managed_files":[]}\n',
        "scripts/installed-tests/test_installed_commands.py": b"print('installed test')\n",
        "VERSION": f"{version}\n".encode(),
        "config/title-preferences.json": b"{}\n",
    }
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, value in files.items():
            info = tarfile.TarInfo(f"caps-productivity-kit-{version}/{name}")
            info.size = len(value)
            archive.addfile(info, io.BytesIO(value))
    return raw.getvalue()


def manifest(archive: bytes, **overrides) -> dict:
    value = {
        "schema_version": "1.0",
        "channel": "stable",
        "version": "0.3.2",
        "artifact_url": "https://example.invalid/release.tar.gz",
        "artifact_sha256": digest(archive),
        "install_schema_min": "1.0",
        "install_schema_max": "1.0",
        "minimum_updater_version": "0.3.0",
        "disruptive": False,
        "release_notes_url": "https://example.invalid/release",
        "rollback_version": "0.2.0",
    }
    value.update(overrides)
    return value


class CapsUpdateTests(unittest.TestCase):
    def test_release_archive_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "one.tar.gz"
            second = root / "two.tar.gz"
            first_hash = BUILD.build_archive(ROOT, first, "0.3.2")
            second_hash = BUILD.build_archive(ROOT, second, "0.3.2")
            self.assertEqual(first_hash, second_hash)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_new_release_remains_installable_by_previous_updater(self):
        value = BUILD.build_manifest(
            version="0.3.2",
            artifact=Path("caps-productivity-kit-0.3.2.tar.gz"),
            digest="a" * 64,
        )
        self.assertEqual(value["minimum_updater_version"], "0.3.0")
        self.assertEqual(value["rollback_version"], "0.3.2")
        self.assertIsNone(UPDATE.compatibility_error(value, "1.0"))

    def test_v032_updater_produces_a_verifiable_v033_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous_source = subprocess.run(
                ["git", "show", "v0.3.2:scripts/caps-update.py"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            previous_path = root / "caps-update-0.3.2.py"
            previous_path.write_text(previous_source, encoding="utf-8")
            previous_spec = importlib.util.spec_from_file_location("caps_update_032", previous_path)
            previous = importlib.util.module_from_spec(previous_spec)
            assert previous_spec.loader
            previous_spec.loader.exec_module(previous)

            archive_path = root / "caps-productivity-kit-0.3.3.tar.gz"
            BUILD.build_archive(ROOT, archive_path, "0.3.3")
            archive = archive_path.read_bytes()
            project = self.make_project(root)
            preferences = project / ".caps/config/title-preferences.json"
            preferences.parent.mkdir(parents=True, exist_ok=True)
            preferences.write_text("{}\n", encoding="utf-8")
            original_fetch = previous.fetch_bytes
            try:
                previous.fetch_bytes = lambda _url: archive
                result = previous.apply_update(
                    project,
                    manifest(archive, version="0.3.3"),
                    allow_disruptive=False,
                )
            finally:
                previous.fetch_bytes = original_fetch

            self.assertEqual(result["status"], "updated")
            installed_verify = subprocess.run(
                [str(project / ".caps/scripts/verify.sh")],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed_verify.returncode, 0, installed_verify.stderr)
            self.assertIn("CAPS installed layout verification passed.", installed_verify.stdout)

    def make_project(self, root: Path, local_docs: bytes = b"old docs\n") -> Path:
        project = root / "project"
        caps = project / ".caps"
        (caps / "docs").mkdir(parents=True)
        (caps / "docs/example.md").write_bytes(local_docs)
        (caps / "install-manifest.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "version": "0.2.0",
                "channel": "stable",
                "managed_files": {"docs/example.md": digest(b"old docs\n")},
            }),
            encoding="utf-8",
        )
        return project

    def test_compatibility_gate(self):
        error = UPDATE.compatibility_error(
            manifest(release_archive(), install_schema_min="2.0"),
            "1.0",
        )
        self.assertEqual(error, "installed_schema_too_old")

    def test_apply_preserves_local_override_and_updates_safe_files(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary), local_docs=b"owner override\n")
            original_fetch = UPDATE.fetch_bytes
            try:
                UPDATE.fetch_bytes = lambda _url: archive
                result = UPDATE.apply_update(project, manifest(archive), allow_disruptive=False)
            finally:
                UPDATE.fetch_bytes = original_fetch
            self.assertEqual(result["status"], "updated")
            self.assertEqual(
                (project / ".caps/docs/example.md").read_bytes(),
                b"owner override\n",
            )
            self.assertIn("docs/example.md", result["local_overrides_preserved"])
            self.assertTrue((project / ".caps/scripts/example.py").exists())
            self.assertTrue(
                (project / ".caps/scripts/installed-tests/test_installed_commands.py").exists()
            )
            installed = json.loads(
                (project / ".caps/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(installed["managed_files"]["docs/example.md"], digest(b"new docs\n"))

    def test_apply_records_incoming_baseline_for_preexisting_unmanaged_override(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            script = project / ".caps/scripts/example.py"
            script.parent.mkdir(parents=True)
            script.write_bytes(b"owner script\n")
            original_fetch = UPDATE.fetch_bytes
            try:
                UPDATE.fetch_bytes = lambda _url: archive
                result = UPDATE.apply_update(project, manifest(archive), allow_disruptive=False)
            finally:
                UPDATE.fetch_bytes = original_fetch

            self.assertEqual(result["status"], "updated")
            self.assertEqual(script.read_bytes(), b"owner script\n")
            installed = json.loads(
                (project / ".caps/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                installed["managed_files"]["scripts/example.py"],
                digest(b"print('ok')\n"),
            )
            self.assertIn("scripts/example.py", installed["local_overrides"])

    def test_apply_adopts_matching_release_bytes_without_overwrite_or_override(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary), local_docs=b"new docs\n")
            docs = project / ".caps/docs/example.md"
            original_timestamp_ns = 1_700_000_000_000_000_000
            os.utime(docs, ns=(original_timestamp_ns, original_timestamp_ns))
            original_fetch = UPDATE.fetch_bytes
            try:
                UPDATE.fetch_bytes = lambda _url: archive
                result = UPDATE.apply_update(project, manifest(archive), allow_disruptive=False)
            finally:
                UPDATE.fetch_bytes = original_fetch

            self.assertEqual(result["status"], "updated")
            self.assertEqual(docs.read_bytes(), b"new docs\n")
            self.assertEqual(docs.stat().st_mtime_ns, original_timestamp_ns)
            self.assertNotIn("docs/example.md", result["updated_files"])
            self.assertNotIn("docs/example.md", result["local_overrides_preserved"])
            installed = json.loads(
                (project / ".caps/install-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(installed["managed_files"]["docs/example.md"], digest(b"new docs\n"))
            self.assertNotIn("docs/example.md", installed["local_overrides"])

    def test_digest_failure_keeps_installed_files(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            original_fetch = UPDATE.fetch_bytes
            try:
                UPDATE.fetch_bytes = lambda _url: archive
                result = UPDATE.apply_update(
                    project,
                    manifest(archive, artifact_sha256="0" * 64),
                    allow_disruptive=False,
                )
            finally:
                UPDATE.fetch_bytes = original_fetch
            self.assertEqual(result["status"], "failed")
            self.assertEqual((project / ".caps/docs/example.md").read_bytes(), b"old docs\n")

    def test_copy_failure_rolls_back_partial_update(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            original_fetch = UPDATE.fetch_bytes
            original_copy = UPDATE.shutil.copy2

            def fail_release_script_copy(source, target):
                source_path = Path(source)
                if source_path.name == "example.py" and "unpacked" in source_path.parts:
                    raise OSError("simulated copy failure")
                return original_copy(source, target)

            try:
                UPDATE.fetch_bytes = lambda _url: archive
                UPDATE.shutil.copy2 = fail_release_script_copy
                result = UPDATE.apply_update(project, manifest(archive), allow_disruptive=False)
            finally:
                UPDATE.fetch_bytes = original_fetch
                UPDATE.shutil.copy2 = original_copy
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["rollback_applied"])
            self.assertEqual((project / ".caps/docs/example.md").read_bytes(), b"old docs\n")
            self.assertFalse((project / ".caps/scripts/example.py").exists())
            installed = json.loads((project / ".caps/install-manifest.json").read_text())
            self.assertEqual(installed["version"], "0.2.0")

    def test_disruptive_update_requires_confirmation(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            result = UPDATE.apply_update(
                project,
                manifest(archive, disruptive=True),
                allow_disruptive=False,
            )
            self.assertEqual(result["status"], "confirmation_required")

    def test_rollback_restores_previous_files_and_manifest(self):
        archive = release_archive()
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            original_fetch = UPDATE.fetch_bytes
            try:
                UPDATE.fetch_bytes = lambda _url: archive
                result = UPDATE.apply_update(project, manifest(archive), allow_disruptive=False)
            finally:
                UPDATE.fetch_bytes = original_fetch
            self.assertEqual((project / ".caps/docs/example.md").read_bytes(), b"new docs\n")
            rolled_back = UPDATE.rollback(project)
            self.assertEqual(rolled_back["status"], "rolled_back")
            self.assertEqual((project / ".caps/docs/example.md").read_bytes(), b"old docs\n")
            self.assertFalse((project / ".caps/scripts/example.py").exists())
            installed = json.loads((project / ".caps/install-manifest.json").read_text())
            self.assertEqual(installed["version"], "0.2.0")


if __name__ == "__main__":
    unittest.main()
