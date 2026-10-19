from __future__ import annotations

import pytest

import yantra.cli as cli


def test_version_and_help_expose_public_commands(capsys) -> None:
    with pytest.raises(SystemExit) as version_exit:
        cli.run_cli(["--version"])
    assert version_exit.value.code == 0
    assert "yantra 0.2.0" in capsys.readouterr().out

    with pytest.raises(SystemExit) as help_exit:
        cli.run_cli(["--help"])
    assert help_exit.value.code == 0
    output = capsys.readouterr().out
    for command in ("doctor", "providers", "models", "quickstart"):
        assert command in output


def test_doctor_reports_env_credentials_without_disclosing_values(monkeypatch, capsys) -> None:
    secret = "cli-doctor-secret-canary"
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", secret)
    monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)

    assert cli.run_cli(["doctor"]) == 0

    output = capsys.readouterr().out
    assert "Provider opencode-zen credential: configured (value hidden)" in output
    assert "Provider opencode-go credential: not configured" in output
    assert "not probed" in output
    assert secret not in output


def test_doctor_reports_missing_required_dependency_as_failure(monkeypatch, capsys) -> None:
    original_version = cli.importlib.metadata.version

    def missing_httpcore(name: str) -> str:
        if name == "httpcore":
            raise cli.importlib.metadata.PackageNotFoundError(name)
        return original_version(name)

    monkeypatch.setattr(cli.importlib.metadata, "version", missing_httpcore)
    assert cli.run_cli(["doctor"]) == 1
    output = capsys.readouterr().out
    assert "Dependency httpcore: FAIL" in output
    assert "installation problems found" in output


def test_doctor_treats_keyring_as_optional(monkeypatch, capsys) -> None:
    original_version = cli.importlib.metadata.version

    def without_keyring(name: str) -> str:
        if name == "keyring":
            raise cli.importlib.metadata.PackageNotFoundError(name)
        return original_version(name)

    monkeypatch.setattr(cli.importlib.metadata, "version", without_keyring)
    assert cli.run_cli(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "Optional dependency keyring: not installed" in output
    assert "installation checks passed" in output


def test_doctor_ollama_probe_is_explicit_local_and_bounded(monkeypatch, capsys) -> None:
    calls: list[tuple[str, object]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self, **kwargs: object) -> None:
            calls.append(("client", kwargs))

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, url: str) -> Response:
            calls.append(("get", url))
            return Response()

    monkeypatch.setattr(cli.httpx, "Client", Client)
    assert cli.run_cli(["doctor", "--check-ollama"]) == 0
    assert calls[1] == ("get", "http://127.0.0.1:11434/api/tags")
    options = calls[0][1]
    assert isinstance(options, dict)
    assert options["trust_env"] is False
    assert options["timeout"].connect == 0.5
    assert "Ollama: responding" in capsys.readouterr().out


def test_providers_reuses_existing_registry(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "run_smoke_cli", lambda args: calls.append(args) or 0)
    assert cli.run_cli(["providers"]) == 0
    assert calls == [["providers"]]


def test_models_are_offline_unless_live_is_explicit(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(cli, "run_smoke_cli", lambda args: calls.append(args) or 0)
    assert cli.run_cli(["models", "ollama"]) == 0
    output = capsys.readouterr().out
    assert "No network request made" in output
    assert calls == []

    assert cli.run_cli(["models", "ollama", "--live"]) == 0
    assert calls == [["models", "ollama"]]


def test_models_live_requires_provider() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.run_cli(["models", "--live"])
    assert exit_info.value.code == 2


def test_quickstart_completes_offline_agent_tool_cycle(capsys) -> None:
    assert cli.run_cli(["quickstart"]) == 0
    output = capsys.readouterr().out
    assert "no credentials or network requests" in output
    assert "Model tool proposal: calculator.add" in output
    assert "Tool result: {'total': 20}" in output
    assert "Final model response: 12 + 8 = 20. The sum is 20." in output


def test_invalid_command_returns_argparse_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.run_cli(["not-a-command"])
    assert exit_info.value.code == 2
