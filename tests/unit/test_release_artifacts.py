from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from yantra.devtools.artifacts import ArtifactVerificationError, verify_artifacts


def _make_artifacts(directory: Path, *, extra_wheel_file: str | None = None) -> None:
    wheel_path = directory / "yantra-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as archive:
        archive.writestr("yantra/__init__.py", "__version__ = '0.2.0'\n")
        archive.writestr("yantra/cli.py", "")
        archive.writestr("yantra/py.typed", "")
        archive.writestr("yantra/devtools/quickstart.py", "")
        archive.writestr("yantra/devtools/smoke.py", "")
        archive.writestr("yantra/devtools/artifacts.py", "")
        archive.writestr(
            "yantra-0.2.0.dist-info/METADATA",
            "Name: yantra\nVersion: 0.2.0\nRequires-Python: >=3.12\n"
            "License-Expression: Apache-2.0\n",
        )
        archive.writestr("yantra-0.2.0.dist-info/WHEEL", "Tag: py3-none-any\n")
        archive.writestr("yantra-0.2.0.dist-info/licenses/LICENSE", "Apache-2.0")
        archive.writestr(
            "yantra-0.2.0.dist-info/entry_points.txt",
            "[console_scripts]\nyantra = yantra.cli:main\n"
            "yantra-smoke = yantra.devtools.smoke:main\n",
        )
        if extra_wheel_file is not None:
            archive.writestr(extra_wheel_file, "synthetic")

    sdist_path = directory / "yantra-0.2.0.tar.gz"
    required = (
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
    )
    with tarfile.open(sdist_path, "w:gz") as archive:
        for relative_name in required:
            data = b"test artifact content"
            info = tarfile.TarInfo(f"yantra-0.2.0/{relative_name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_verifier_checks_expected_distributions_and_writes_sha256(tmp_path: Path) -> None:
    _make_artifacts(tmp_path)

    wheel, sdist, checksums = verify_artifacts(tmp_path)

    expected_lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (wheel, sdist)
    ]
    assert checksums.read_text(encoding="ascii").splitlines() == expected_lines


def test_verifier_rejects_secret_files_in_artifact(tmp_path: Path) -> None:
    _make_artifacts(tmp_path, extra_wheel_file="yantra/.env")

    with pytest.raises(ArtifactVerificationError, match="secret configuration"):
        verify_artifacts(tmp_path)


def test_verifier_rejects_missing_distribution(tmp_path: Path) -> None:
    with pytest.raises(ArtifactVerificationError, match="pure Python wheel"):
        verify_artifacts(tmp_path)


def test_verifier_checks_existing_checksum_manifest_without_overwriting(tmp_path: Path) -> None:
    _make_artifacts(tmp_path)
    checksum_path = tmp_path / "SHA256SUMS.txt"
    checksum_path.write_text("incorrect\n", encoding="ascii")

    with pytest.raises(ArtifactVerificationError, match="do not match"):
        verify_artifacts(tmp_path)

    assert checksum_path.read_text(encoding="ascii") == "incorrect\n"
