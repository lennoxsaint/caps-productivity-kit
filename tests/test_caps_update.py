from __future__ import annotations

import hashlib
import importlib.util
import io
import json
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


def release_archive(version: str = "0.3.1") -> bytes:
    files = {
        "automations/example.toml": b"status = \"PAUSED\"\n",
        "docs/example.md": b"new docs\n",
        "examples/example.md": b"example\n",
        "prompts/example.md": b"prompt\n",
        "prompts/bootstrap-caps-conductor.md": b"bootstrap\n",
        "schemas/example.json": b"{}\n",
        "scripts/example.py": b"print('ok')\n",
        "templates/example.md": b"template\n",
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
        "version": "0.3.1",
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
            first_hash = BUILD.build_archive(ROOT, first, "0.3.1")
            second_hash = BUILD.build_archive(ROOT, second, "0.3.1")
            self.assertEqual(first_hash, second_hash)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_new_release_remains_installable_by_previous_updater(self):
        value = BUILD.build_manifest(
            version="0.3.1",
            artifact=Path("caps-productivity-kit-0.3.1.tar.gz"),
            digest="a" * 64,
        )
        self.assertEqual(value["minimum_updater_version"], "0.3.0")
        self.assertEqual(value["rollback_version"], "0.3.0")
        self.assertIsNone(UPDATE.compatibility_error(value, "1.0"))

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
