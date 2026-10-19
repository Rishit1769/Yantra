"""Developer-facing command line interface for YANTRA."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import sys
from collections.abc import Sequence

import httpx

from yantra import __version__
from yantra.devtools.quickstart import run_quickstart
from yantra.devtools.smoke import run_cli as run_smoke_cli

_PROVIDERS = ("ollama", "opencode-zen", "opencode-go")
_CREDENTIAL_ENV = {
    "opencode-zen": "OPENCODE_ZEN_API_KEY",
    "opencode-go": "OPENCODE_GO_API_KEY",
}
_REQUIRED_DISTRIBUTIONS = ("httpcore", "httpx", "pydantic")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yantra",
        description=(
            "Install, inspect, and try YANTRA locally. Model discovery is offline by default; "
            "the quickstart never contacts a provider."
        ),
    )
    parser.add_argument("--version", action="version", version=f"yantra {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="check the local Python installation")
    doctor.add_argument(
        "--check-ollama",
        action="store_true",
        help="make a bounded HTTP check to local Ollama at 127.0.0.1:11434",
    )
    commands.add_parser("providers", help="show supported provider configuration (no network)")

    models = commands.add_parser("models", help="show providers or fetch a live model catalog")
    models.add_argument("provider", nargs="?", choices=_PROVIDERS)
    models.add_argument(
        "--live",
        action="store_true",
        help="explicitly request the provider's live catalog (no inference)",
    )

    commands.add_parser("quickstart", help="run the deterministic offline agent demonstration")
    return parser


def _doctor(*, check_ollama: bool) -> int:
    failures = 0
    python_ok = sys.version_info >= (3, 12)
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"Python: {'OK' if python_ok else 'FAIL'} ({python_version})")
    if not python_ok:
        print("  YANTRA requires Python 3.12 or newer.")
        failures += 1

    print(f"YANTRA: {__version__}")
    for distribution in _REQUIRED_DISTRIBUTIONS:
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            print(f"Dependency {distribution}: FAIL (not installed)")
            failures += 1
        else:
            print(f"Dependency {distribution}: OK ({version})")
    try:
        keyring_version = importlib.metadata.version("keyring")
    except importlib.metadata.PackageNotFoundError:
        print("Optional dependency keyring: not installed (only needed for keyring:// references)")
    else:
        print(f"Optional dependency keyring: installed ({keyring_version})")

    for provider_id, variable in _CREDENTIAL_ENV.items():
        status = (
            "configured (value hidden)"
            if _environment_credential_present(variable)
            else "not configured"
        )
        print(f"Provider {provider_id} credential: {status}")
    print("Provider ollama: local endpoint; credentials not required")

    if check_ollama:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(0.8, connect=0.5),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = client.get("http://127.0.0.1:11434/api/tags")
                response.raise_for_status()
        except httpx.HTTPError:
            print("Ollama: unavailable at 127.0.0.1:11434 (optional)")
        else:
            print("Ollama: responding at 127.0.0.1:11434")
    else:
        print("Ollama: not probed (use --check-ollama for a bounded loopback check)")

    print(
        "Doctor: "
        + ("installation checks passed" if not failures else "installation problems found")
    )
    return int(failures > 0)


def _environment_credential_present(variable: str) -> bool:
    """Check only whether the configured environment variable is non-empty."""
    return bool(os.environ.get(variable))


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the public developer CLI and return its process status."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _doctor(check_ollama=args.check_ollama)
    if args.command == "providers":
        return run_smoke_cli(["providers"])
    if args.command == "models":
        if args.live:
            if args.provider is None:
                parser.error("models --live requires a provider")
            return run_smoke_cli(["models", args.provider])
        if args.provider is not None:
            print(f"No network request made. Re-run with --live to query {args.provider}.")
        else:
            print("Model discovery is live and opt-in. Available providers:")
            for provider in _PROVIDERS:
                print(f"- {provider}")
            print("Use: yantra models PROVIDER --live")
        return 0
    if args.command == "quickstart":
        return run_quickstart()
    parser.error("unknown command")
    return 2


def main() -> None:
    """Console-script entry point."""
    raise SystemExit(run_cli())
