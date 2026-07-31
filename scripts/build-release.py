#!/usr/bin/env python3
"""Build a deterministic CAPS release artifact and channel manifest."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", "channels", "dist", "__pycache__"}
MINIMUM_UPDATER_VERSION = "0.3.0"
ROLLBACK_VERSION = "0.3.1"


def release_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and not (set(path.relative_to(root).parts) & EXCLUDED_PARTS)
        and path.suffix != ".pyc"
    )


def build_archive(root: Path, output: Path, version: str) -> str:
    prefix = f"caps-productivity-kit-{version}"
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in release_files(root):
            relative = path.relative_to(root)
            info = archive.gettarinfo(str(path), arcname=f"{prefix}/{relative}")
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(buffer.getvalue())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def build_manifest(version: str, artifact: Path, digest: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "channel": "stable",
        "version": version,
        "artifact_url": (
            "https://github.com/lennoxsaint/caps-productivity-kit/"
            f"releases/download/v{version}/{artifact.name}"
        ),
        "artifact_sha256": digest,
        "install_schema_min": "1.0",
        "install_schema_max": "1.0",
        "minimum_updater_version": MINIMUM_UPDATER_VERSION,
        "disruptive": False,
        "release_notes_url": (
            "https://github.com/lennoxsaint/caps-productivity-kit/"
            f"releases/tag/v{version}"
        ),
        "rollback_version": ROLLBACK_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    artifact = args.output_dir / f"caps-productivity-kit-{version}.tar.gz"
    digest = build_archive(ROOT, artifact, version)
    manifest = build_manifest(version, artifact, digest)
    if args.manifest_output:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"artifact": str(artifact), "sha256": digest, "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
