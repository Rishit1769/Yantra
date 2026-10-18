"""Fixed, isolated-mode worker entry point with a source-controlled handler allowlist."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import uuid
from typing import Any, cast

PROTOCOL_VERSION = 1
MAX_WORKER_REQUEST_BYTES = 64 * 1024
MAX_WORKER_RESPONSE_BYTES = 64 * 1024
WORKER_HANDLER_IDS = frozenset(
    {
        "yantra.demo.echo",
        "yantra.demo.concat",
        "yantra.demo.block",
        "yantra.demo.large_response",
        "yantra.demo.tool_error",
        "yantra.demo.crash",
    }
)


def _echo(arguments: dict[str, Any]) -> Any:
    return arguments


def _concat(arguments: dict[str, Any]) -> dict[str, str]:
    left = arguments.get("left")
    right = arguments.get("right")
    if not isinstance(left, str) or not isinstance(right, str):
        raise ValueError("handler input mismatch")
    return {"value": left + right}


def _block(arguments: dict[str, Any]) -> None:
    del arguments
    threading.Event().wait()
    return None


def _large_response(arguments: dict[str, Any]) -> dict[str, str]:
    del arguments
    return {"value": "x" * (MAX_WORKER_RESPONSE_BYTES + 1024)}


def _tool_error(arguments: dict[str, Any]) -> None:
    del arguments
    raise ValueError("worker handler failure")


def _crash(arguments: dict[str, Any]) -> None:
    del arguments
    os._exit(23)


_HANDLERS = {
    "yantra.demo.echo": _echo,
    "yantra.demo.concat": _concat,
    "yantra.demo.block": _block,
    "yantra.demo.large_response": _large_response,
    "yantra.demo.tool_error": _tool_error,
    "yantra.demo.crash": _crash,
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _emit(response: dict[str, Any]) -> None:
    encoded = json.dumps(response, sort_keys=True, separators=(",", ":"), allow_nan=False)
    data = encoded.encode("utf-8", errors="strict")
    if len(data) > MAX_WORKER_RESPONSE_BYTES:
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "invocation_id": response["invocation_id"],
            "status": "tool_error",
            "error_category": "response_too_large",
        }
        data = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(data + b"\n")
    sys.stdout.buffer.flush()


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_WORKER_REQUEST_BYTES + 1)
    if len(raw) > MAX_WORKER_REQUEST_BYTES:
        return 64
    try:
        parsed: Any = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
        if not isinstance(parsed, dict) or set(cast(dict[str, Any], parsed)) != {
            "protocol_version",
            "invocation_id",
            "handler_id",
            "arguments",
        }:
            return 65
        request = cast(dict[str, Any], parsed)
        if type(request["protocol_version"]) is not int or request["protocol_version"] != 1:
            return 65
        request_invocation_id = request["invocation_id"]
        if not isinstance(request_invocation_id, str):
            return 65
        invocation_id = str(uuid.UUID(request_invocation_id))
        handler_id = request["handler_id"]
        raw_arguments = request["arguments"]
        if not isinstance(handler_id, str) or not isinstance(raw_arguments, dict):
            return 65
        arguments = cast(dict[str, Any], raw_arguments)
        handler = _HANDLERS.get(handler_id)
        if handler is None:
            return 65
    except Exception:
        return 65

    try:
        with contextlib.redirect_stdout(sys.stderr):
            value = handler(arguments)
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "invocation_id": invocation_id,
            "status": "succeeded",
            "value": value,
        }
    except Exception:
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "invocation_id": invocation_id,
            "status": "tool_error",
            "error_category": "tool_exception",
        }
    try:
        _emit(response)
    except Exception:
        return 66
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
