# Release artifact verification

The release-candidate workflow builds a wheel and source distribution, checks
metadata and archive contents, writes `SHA256SUMS.txt`, tests fresh installs,
and uploads a short-lived GitHub Actions artifact. This is CI artifact storage,
not a GitHub Release or package-index publication. Artifacts expire according
to workflow/repository retention.

## Download and verify checksums

Download the `yantra-<commit-sha>` artifact from the corresponding successful
**Release Candidate Verification** run. Keep the wheel, sdist, and checksum
file from the same artifact together. From a source checkout at the same
candidate, run the portable verifier with Python 3.12 or newer:

```sh
uv sync --locked --all-groups
uv run python scripts/verify_release_artifacts.py --dist /path/to/downloaded/artifacts
```

The script verifies the expected versioned wheel and sdist names, wheel
metadata (`Name`, version, `Requires-Python`, SPDX license expression and
`py3-none-any` tag), both console entry points, required source files, and
absence of common secret/cache/build files. If `SHA256SUMS.txt` is already
present, it compares the computed hashes against that manifest without
overwriting it; if absent, it creates the manifest.

Portable standard-library checksum checks are also available. On macOS:

```sh
shasum -a 256 -c SHA256SUMS.txt
```

On Windows PowerShell, read the manifest and compare each listed digest with
`(Get-FileHash .\<filename> -Algorithm SHA256).Hash.ToLowerInvariant()`. Keep
the checksum manifest adjacent to the exact downloaded files. SHA-256 detects
corruption/mismatch; it does not authenticate who built the artifact.

## Install each distribution independently

Use fresh virtual environments outside the source repository. Do not install
from the current checkout when verifying a downloaded artifact. On macOS:

```sh
python3.12 -m venv /tmp/yantra-wheel-check
/tmp/yantra-wheel-check/bin/python -m pip install ./yantra-0.2.0-py3-none-any.whl
cd /tmp
/tmp/yantra-wheel-check/bin/yantra --version
/tmp/yantra-wheel-check/bin/yantra doctor
/tmp/yantra-wheel-check/bin/yantra quickstart

python3.12 -m venv /tmp/yantra-sdist-check
/tmp/yantra-sdist-check/bin/python -m pip install ./yantra-0.2.0.tar.gz
cd /tmp
/tmp/yantra-sdist-check/bin/yantra --version
/tmp/yantra-sdist-check/bin/yantra quickstart
```

On Windows, use distinct venvs and invoke their executables directly, for
example `.\.wheel-check\Scripts\python.exe -m pip install .\yantra-0.2.0-py3-none-any.whl`
then `.\.wheel-check\Scripts\yantra.exe quickstart`. Repeat with the sdist
in another fresh environment. Running from outside the checkout verifies
that imports and entry points come from the installed distribution.

The workflow verifies wheel/sdist metadata, archive completeness, CLI scripts,
offline quickstart, smoke CLI, and SHA-256. No signing or supply-chain
attestation is implemented or implied. Builds are validated as functional
artifacts; exact bit-for-bit reproducibility should only be claimed for a
specific repeated-build comparison under equivalent toolchains.
