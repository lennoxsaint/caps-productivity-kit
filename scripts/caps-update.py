#!/usr/bin/env python3
"""Check, safely apply, or roll back a versioned CAPS kit update."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UPDATER_VERSION = "0.3.3"
DEFAULT_CHANNEL_URL = (
    "https://raw.githubusercontent.com/lennoxsaint/"
    "caps-productivity-kit/main/channels/stable.json"
)
INSTALL_SCHEMA = "1.0"
INSTALL_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config/installed-files.json"


def source_mappings() -> dict[str, str]:
    contract = read_json(INSTALL_CONTRACT_PATH)
    mappings = contract.get("source_mappings")
    if not isinstance(mappings, dict) or any(
        not isinstance(source, str) or not isinstance(target, str)
        for source, target in mappings.items()
    ):
        raise RuntimeError("invalid_install_contract_source_mappings")
    return mappings


def version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as error:
        raise ValueError(f"invalid version: {value}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        if default is None:
            raise FileNotFoundError(path)
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"caps-update/{UPDATER_VERSION}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_manifest(url: str) -> dict[str, Any]:
    try:
        value = json.loads(fetch_bytes(url))
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"channel_unavailable: {error}") from error
    required = {
        "schema_version", "channel", "version", "artifact_url", "artifact_sha256",
        "install_schema_min", "install_schema_max", "minimum_updater_version",
        "disruptive", "release_notes_url", "rollback_version",
    }
    if not isinstance(value, dict) or required - value.keys():
        raise RuntimeError(f"invalid_channel_manifest: missing {sorted(required - set(value or {}))}")
    if value["schema_version"] != "1.0":
        raise RuntimeError("unsupported_channel_schema")
    return value


def compatibility_error(manifest: dict[str, Any], installed_schema: str) -> str | None:
    if version_tuple(UPDATER_VERSION) < version_tuple(str(manifest["minimum_updater_version"])):
        return "updater_too_old"
    installed = version_tuple(installed_schema)
    if installed < version_tuple(str(manifest["install_schema_min"])):
        return "installed_schema_too_old"
    if installed > version_tuple(str(manifest["install_schema_max"])):
        return "installed_schema_too_new"
    return None


def status_path(project: Path) -> Path:
    return project / ".caps/state/update-status.json"


def write_status(project: Path, **values: Any) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **values,
    }
    atomic_json(status_path(project), payload)
    return payload


def safe_extract(archive: Path, destination: Path) -> Path:
    destination_resolved = destination.resolve()
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            target = (destination / member.name).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise RuntimeError("unsafe_archive_path")
            if member.issym() or member.islnk():
                raise RuntimeError("archive_links_not_allowed")
            if not (member.isfile() or member.isdir()):
                raise RuntimeError("unsupported_archive_member")
        source.extractall(destination, members=members)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError("invalid_release_layout")
    return roots[0]


def release_managed_files(release_root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for source_name, target_name in source_mappings().items():
        source = release_root / source_name
        if not source.exists():
            raise RuntimeError(f"release_missing_required_path:{source_name}")
        if source.is_file():
            files[target_name] = source
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                relative = path.relative_to(source)
                files[str(Path(target_name) / relative)] = path
    return files


def check(project: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    installed = read_json(project / ".caps/install-manifest.json", {
        "schema_version": INSTALL_SCHEMA,
        "version": "0.0.0",
        "managed_files": {},
    })
    blocker = compatibility_error(manifest, str(installed.get("schema_version", INSTALL_SCHEMA)))
    current = str(installed.get("version", "0.0.0"))
    available = str(manifest["version"])
    result = {
        "status": "blocked" if blocker else ("update_available" if version_tuple(available) > version_tuple(current) else "current"),
        "installed_version": current,
        "available_version": available,
        "channel": manifest["channel"],
        "disruptive": bool(manifest["disruptive"]),
        "blocker": blocker,
        "release_notes_url": manifest["release_notes_url"],
    }
    write_status(project, **result)
    return result


def restore_backup(caps: Path, backup_root: Path, created: list[str]) -> None:
    for relative in created:
        target = caps / relative
        if target.is_file():
            target.unlink()
    files = backup_root / "files"
    if files.exists():
        for source in files.rglob("*"):
            if source.is_file():
                target = caps / source.relative_to(files)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    manifest_backup = backup_root / "install-manifest.json"
    if manifest_backup.exists():
        shutil.copy2(manifest_backup, caps / "install-manifest.json")


def apply_update(project: Path, manifest: dict[str, Any], allow_disruptive: bool) -> dict[str, Any]:
    checked = check(project, manifest)
    if checked["status"] != "update_available":
        return checked
    if manifest["disruptive"] and not allow_disruptive:
        stopped = {
            **checked,
            "status": "confirmation_required",
            "blocker": "disruptive_update",
        }
        return write_status(project, **stopped)

    caps = project / ".caps"
    installed_path = caps / "install-manifest.json"
    installed = read_json(installed_path)
    expected = dict(installed.get("managed_files", {}))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = caps / "state/update-backups" / stamp
    updated: list[str] = []
    preserved: list[str] = []
    created: list[str] = []

    with tempfile.TemporaryDirectory(prefix="caps-update-") as temporary_name:
        temporary = Path(temporary_name)
        archive = temporary / "release.tar.gz"
        archive.write_bytes(fetch_bytes(str(manifest["artifact_url"])))
        actual_digest = sha256(archive)
        if actual_digest != manifest["artifact_sha256"]:
            return write_status(
                project,
                status="failed",
                installed_version=installed.get("version"),
                available_version=manifest["version"],
                blocker="artifact_digest_mismatch",
                expected_sha256=manifest["artifact_sha256"],
                actual_sha256=actual_digest,
            )
        release_root = safe_extract(archive, temporary / "unpacked")
        release_files = release_managed_files(release_root)

        backup_root.mkdir(parents=True, exist_ok=False)
        if installed_path.exists():
            destination = backup_root / "install-manifest.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installed_path, destination)
        new_hashes = dict(expected)
        try:
            for relative, source in release_files.items():
                target = caps / relative
                source_hash = sha256(source)
                if target.exists():
                    current_hash = sha256(target)
                    installed_hash = expected.get(relative)
                    if installed_hash is None:
                        preserved.append(relative)
                        new_hashes[relative] = source_hash
                        continue
                    if current_hash != installed_hash:
                        if current_hash == source_hash:
                            new_hashes[relative] = source_hash
                            continue
                        preserved.append(relative)
                        new_hashes[relative] = source_hash
                        continue
                    backup = backup_root / "files" / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                else:
                    created.append(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                new_hashes[relative] = source_hash
                updated.append(relative)

            new_manifest = {
                "schema_version": INSTALL_SCHEMA,
                "version": manifest["version"],
                "channel": manifest["channel"],
                "source_repository": "https://github.com/lennoxsaint/caps-productivity-kit",
                "managed_files": new_hashes,
                "local_overrides": sorted(preserved),
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json(installed_path, new_manifest)
        except OSError as error:
            restore_backup(caps, backup_root, created)
            return write_status(
                project,
                status="failed",
                installed_version=installed.get("version"),
                available_version=manifest["version"],
                blocker=f"apply_failed:{type(error).__name__}",
                rollback_applied=True,
            )
    return write_status(
        project,
        status="updated",
        installed_version=manifest["version"],
        available_version=manifest["version"],
        backup_dir=str(backup_root),
        updated_files=updated,
        created_files=created,
        local_overrides_preserved=preserved,
        release_notes_url=manifest["release_notes_url"],
    )


def rollback(project: Path) -> dict[str, Any]:
    status = read_json(status_path(project))
    backup_value = status.get("backup_dir")
    if not backup_value:
        raise RuntimeError("rollback_unavailable")
    backup = Path(str(backup_value))
    caps = project / ".caps"
    if not backup.is_dir() or caps.resolve() not in backup.resolve().parents:
        raise RuntimeError("invalid_rollback_path")
    restore_backup(caps, backup, [str(item) for item in status.get("created_files", [])])
    restored = read_json(caps / "install-manifest.json")
    return write_status(
        project,
        status="rolled_back",
        installed_version=restored.get("version"),
        available_version=status.get("available_version"),
        rollback_source=str(backup),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--allow-disruptive", action="store_true")
    sub.add_parser("rollback")
    args = parser.parse_args()
    project = args.project.resolve()
    try:
        if args.command == "rollback":
            result = rollback(project)
        else:
            manifest = fetch_manifest(args.channel_url)
            result = check(project, manifest) if args.command == "check" else apply_update(
                project,
                manifest,
                args.allow_disruptive,
            )
    except (OSError, RuntimeError, ValueError) as error:
        result = write_status(
            project,
            status="failed",
            installed_version=None,
            available_version=None,
            blocker=str(error),
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("status") in {"blocked", "failed", "confirmation_required"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
