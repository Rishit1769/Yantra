"""Inspect YANTRA wheel/sdist contents and write portable SHA-256 checksums."""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath

from yantra import __version__


class ArtifactVerificationError(Exception):
    """An artifact is missing, malformed, or contains an unintended file."""


def _validate_archive_path(name: str) -> None:
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ArtifactVerificationError(f"unsafe archive path: {name}")
    if path.parts and ":" in path.parts[0]:
        raise ArtifactVerificationError(f"unsafe archive path: {name}")
    if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
        raise ArtifactVerificationError(f"unintended generated/private path: {name}")
    if path.suffix in {".pyc", ".pyo", ".pem", ".key", ".log"}:
        raise ArtifactVerificationError(f"unintended generated/private file: {name}")
    if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
        raise ArtifactVerificationError(f"unintended secret configuration file: {name}")


def _single_match(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise ArtifactVerificationError(f"expected exactly one {description}; found {len(paths)}")
    return paths[0]


def verify_artifacts(dist_dir: Path, *, version: str = __version__) -> tuple[Path, Path, Path]:
    """Verify expected artifacts and write SHA256SUMS.txt in ``dist_dir``."""
    wheel = _single_match(
        list(dist_dir.glob(f"yantra-{version}-py3-none-any.whl")), "pure Python wheel"
    )
    sdist = _single_match(list(dist_dir.glob(f"yantra-{version}.tar.gz")), "source distribution")
    if not wheel.is_file() or not sdist.is_file():
        raise ArtifactVerificationError("wheel and source distribution must be regular files")
    unexpected_distributions = [
        path
        for pattern, expected in (("*.whl", wheel), ("*.tar.gz", sdist))
        for path in dist_dir.glob(pattern)
        if path != expected
    ]
    if unexpected_distributions:
        raise ArtifactVerificationError("unexpected distribution artifacts are present")

    try:
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = archive.namelist()
            for name in wheel_names:
                _validate_archive_path(name)
            if any(not name.startswith(("yantra/", "yantra-")) for name in wheel_names):
                raise ArtifactVerificationError("wheel contains files outside package metadata")
            metadata_names = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
            wheel_metadata_names = [
                name for name in wheel_names if name.endswith(".dist-info/WHEEL")
            ]
            entry_point_names = [
                name for name in wheel_names if name.endswith(".dist-info/entry_points.txt")
            ]
            license_names = [
                name for name in wheel_names if name.endswith(".dist-info/licenses/LICENSE")
            ]
            if not any(name.startswith("yantra/") for name in wheel_names):
                raise ArtifactVerificationError("wheel does not contain the yantra package")
            required_wheel_files = {
                "yantra/cli.py",
                "yantra/py.typed",
                "yantra/devtools/quickstart.py",
                "yantra/devtools/smoke.py",
                "yantra/devtools/artifacts.py",
            }
            missing_wheel_files = required_wheel_files - set(wheel_names)
            if missing_wheel_files:
                raise ArtifactVerificationError(
                    "wheel is incomplete: " + ", ".join(sorted(missing_wheel_files))
                )
            if (
                len(metadata_names) != 1
                or len(wheel_metadata_names) != 1
                or len(entry_point_names) != 1
                or len(license_names) != 1
            ):
                raise ArtifactVerificationError("wheel metadata files are incomplete or ambiguous")
            metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
            wheel_metadata = archive.read(wheel_metadata_names[0]).decode("utf-8")
            entry_points = archive.read(entry_point_names[0]).decode("utf-8")
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise ArtifactVerificationError("wheel is not a readable Python distribution") from exc

    if metadata.get("Name", "").lower() != "yantra" or metadata.get("Version") != version:
        raise ArtifactVerificationError("wheel project name/version metadata does not match")
    if metadata.get("Requires-Python") != ">=3.12":
        raise ArtifactVerificationError("wheel Python compatibility metadata is incorrect")
    if not metadata.get("License-Expression"):
        raise ArtifactVerificationError("wheel is missing SPDX license-expression metadata")
    if "Tag: py3-none-any" not in wheel_metadata:
        raise ArtifactVerificationError("wheel compatibility tag is not py3-none-any")
    for expected_entry in (
        "yantra = yantra.cli:main",
        "yantra-smoke = yantra.devtools.smoke:main",
    ):
        if expected_entry not in entry_points:
            raise ArtifactVerificationError(
                f"wheel is missing console entry point: {expected_entry}"
            )

    required_sdist = {
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "src/yantra/cli.py",
        "src/yantra/devtools/quickstart.py",
        "src/yantra/devtools/smoke.py",
        "src/yantra/devtools/artifacts.py",
        "tests/unit/test_cli.py",
        "tests/unit/test_release_artifacts.py",
        "docs/features/cli.md",
        "docs/getting-started/installation.md",
        "scripts/verify_release_artifacts.py",
    }
    try:
        with tarfile.open(sdist, mode="r:gz") as archive:
            members = archive.getmembers()
            if any(not member.isfile() and not member.isdir() for member in members):
                raise ArtifactVerificationError(
                    "source distribution contains links or special files"
                )
            names = [member.name for member in members]
            for name in names:
                _validate_archive_path(name)
            relative_names = {"/".join(PurePosixPath(name).parts[1:]) for name in names}
            missing = required_sdist - relative_names
            if missing:
                raise ArtifactVerificationError(
                    "source distribution is incomplete: " + ", ".join(sorted(missing))
                )
            if not any(name.endswith("/LICENSE") for name in names):
                raise ArtifactVerificationError("source distribution is missing LICENSE")
    except (OSError, tarfile.TarError) as exc:
        raise ArtifactVerificationError(
            "source distribution is not a readable gzip tar archive"
        ) from exc

    checksum_path = dist_dir / "SHA256SUMS.txt"
    lines: list[str] = []
    for artifact in (wheel, sdist):
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        lines.append(f"{digest}  {artifact.name}")
    expected_checksums = "\n".join(lines) + "\n"
    if checksum_path.exists():
        try:
            existing_checksums = checksum_path.read_text(encoding="ascii")
        except (OSError, UnicodeDecodeError) as exc:
            raise ArtifactVerificationError("existing checksum manifest is unreadable") from exc
        if existing_checksums != expected_checksums:
            raise ArtifactVerificationError("artifact checksums do not match SHA256SUMS.txt")
    else:
        checksum_path.write_text(expected_checksums, encoding="ascii", newline="\n")
    return wheel, sdist, checksum_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"), help="artifact directory")
    args = parser.parse_args(argv)
    try:
        wheel, sdist, checksums = verify_artifacts(args.dist)
    except ArtifactVerificationError as exc:
        print(f"Artifact verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Verified wheel: {wheel.name}")
    print(f"Verified source distribution: {sdist.name}")
    print(f"SHA-256 checksums: {checksums}")
    return 0
