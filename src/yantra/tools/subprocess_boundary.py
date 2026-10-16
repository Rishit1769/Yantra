"""Fixed-entrypoint subprocess boundary with bounded JSON IPC and child cleanup."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from yantra.tools.base import ToolDefinition
from yantra.tools.execution import (
    ExecutionLimits,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionResult,
    ExecutionResultStatus,
    ToolExecutionBoundaryMode,
)


class _StreamTooLarge(Exception):
    def __init__(self, *, diagnostic: bool) -> None:
        self.diagnostic = diagnostic


class SubprocessExecutionBoundary:
    """Run fixed, trusted worker handlers in a child process; not an OS sandbox."""

    def __init__(self, limits: ExecutionLimits | None = None) -> None:
        self.limits = limits or ExecutionLimits()
        self._workers = asyncio.Semaphore(self.limits.max_concurrent_workers)
        self._active: set[asyncio.subprocess.Process] = set()
        self._worker_script = Path(__file__).with_name("_worker.py").resolve()

    @property
    def active_worker_count(self) -> int:
        return len(self._active)

    async def execute(
        self,
        definition: ToolDefinition,
        arguments: Any,
        *,
        invocation_id: UUID,
        timeout_seconds: float | None,
    ) -> ExecutionResult:
        if definition.execution_boundary != ToolExecutionBoundaryMode.SUBPROCESS:
            return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
        handler_id = definition.worker_handler_id
        if handler_id is None:
            return ExecutionResult(status=ExecutionResultStatus.STARTUP_FAILURE)
        try:
            json_arguments = (
                arguments.model_dump(mode="json") if isinstance(arguments, BaseModel) else arguments
            )
            request = ExecutionRequest(
                protocol_version=1,
                invocation_id=invocation_id,
                handler_id=handler_id,
                arguments=json_arguments,
            )
            serialized = json.dumps(
                request.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8", errors="strict")
        except Exception:
            return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
        if len(serialized) + 1 > self.limits.max_request_bytes:
            return ExecutionResult(status=ExecutionResultStatus.REQUEST_TOO_LARGE)

        timeout = self.limits.max_execution_seconds
        if timeout_seconds is not None:
            timeout = min(timeout, timeout_seconds)
        if timeout <= 0:
            return ExecutionResult(status=ExecutionResultStatus.TIMEOUT)
        if self._workers.locked():
            return ExecutionResult(status=ExecutionResultStatus.WORKER_LIMIT)
        await self._workers.acquire()
        try:
            async with asyncio.timeout(timeout):
                return await self._run_worker(serialized + b"\n", invocation_id)
        except TimeoutError:
            return ExecutionResult(status=ExecutionResultStatus.TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ExecutionResult(status=ExecutionResultStatus.STARTUP_FAILURE)
        finally:
            self._workers.release()

    async def _run_worker(self, request: bytes, invocation_id: UUID) -> ExecutionResult:
        spawn_task = asyncio.create_task(self._spawn_worker())
        try:
            process = await asyncio.shield(spawn_task)
        except asyncio.CancelledError:
            try:
                process = await spawn_task
            except Exception:
                raise
            await self._terminate(process)
            raise
        except OSError:
            return ExecutionResult(status=ExecutionResultStatus.STARTUP_FAILURE)

        self._active.add(process)
        readers: list[asyncio.Task[bytes]] = []
        try:
            if process.stdin is None or process.stdout is None or process.stderr is None:
                return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
            process.stdin.write(request)
            await process.stdin.drain()
            process.stdin.close()
            readers = [
                asyncio.create_task(
                    self._read_bounded(process.stdout, self.limits.max_response_bytes)
                ),
                asyncio.create_task(
                    self._read_bounded(
                        process.stderr,
                        self.limits.max_diagnostic_bytes,
                        diagnostic=True,
                    )
                ),
            ]
            wait_task = asyncio.create_task(process.wait())
            try:
                stdout, _stderr = await asyncio.gather(*readers)
                return_code = await wait_task
            except _StreamTooLarge as exc:
                await self._terminate(process)
                status = (
                    ExecutionResultStatus.PROTOCOL_FAILURE
                    if exc.diagnostic
                    else ExecutionResultStatus.RESPONSE_TOO_LARGE
                )
                return ExecutionResult(status=status)
            if return_code != 0:
                return ExecutionResult(status=ExecutionResultStatus.UNEXPECTED_EXIT)
            try:
                _reject_duplicate_keys(stdout.strip())
                response = ExecutionResponse.model_validate_json(stdout.strip())
            except Exception:
                return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
            if response.invocation_id != invocation_id:
                return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
            if response.status == "tool_error":
                if response.error_category == "response_too_large":
                    return ExecutionResult(status=ExecutionResultStatus.RESPONSE_TOO_LARGE)
                return ExecutionResult(
                    status=ExecutionResultStatus.TOOL_ERROR,
                    error_category=(
                        response.error_category
                        if response.error_category in {"tool_exception", "response_too_large"}
                        else "tool_exception"
                    ),
                )
            return ExecutionResult(
                status=ExecutionResultStatus.SUCCEEDED,
                value=response.value,
            )
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        except (BrokenPipeError, ConnectionError):
            await self._terminate(process)
            return ExecutionResult(status=ExecutionResultStatus.UNEXPECTED_EXIT)
        except Exception:
            await self._terminate(process)
            return ExecutionResult(status=ExecutionResultStatus.PROTOCOL_FAILURE)
        finally:
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)
            if process.returncode is None:
                await self._terminate(process)
            self._active.discard(process)

    async def _spawn_worker(self) -> asyncio.subprocess.Process:
        env = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR")
            if key in os.environ
        }
        env["PATH"] = os.defpath
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-S",
            str(self._worker_script),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tempfile.gettempdir(),
            env=env,
            close_fds=True,
            limit=max(self.limits.max_response_bytes, self.limits.max_diagnostic_bytes) + 1,
        )

    @staticmethod
    async def _read_bounded(
        stream: asyncio.StreamReader, maximum: int, *, diagnostic: bool = False
    ) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await stream.read(min(8192, maximum + 1 - total))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise _StreamTooLarge(diagnostic=diagnostic)

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.stdin is not None and not process.stdin.is_closing():
            process.stdin.close()
        if process.returncode is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        except OSError:
            try:
                process.kill()
            except (ProcessLookupError, OSError):
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=self.limits.termination_grace_seconds)
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()


def _reject_duplicate_keys(payload: bytes) -> None:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    json.loads(
        payload.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
