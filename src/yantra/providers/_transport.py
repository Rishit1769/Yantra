"""HTTP transport enforcing endpoint address policy at connection time."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, cast
from urllib.parse import urlsplit

import httpcore
import httpx

AddressInfo = tuple[Any, Any, Any, Any, tuple[Any, ...]]
AddressResolver = Callable[[str, int], Awaitable[list[AddressInfo]]]


class _EndpointNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        backend: httpcore.AsyncNetworkBackend,
        endpoint_host: str,
        *,
        allow_private_network: bool,
        resolver: AddressResolver | None = None,
    ) -> None:
        self._backend = backend
        self._endpoint_host = _normalize_host(endpoint_host)
        self._loopback_host = _is_loopback_host(self._endpoint_host)
        self._allow_private_network = allow_private_network
        self._resolver = resolver or _resolve_addresses

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if _normalize_host(host) != self._endpoint_host:
            raise httpcore.ConnectError("connection host does not match trusted provider endpoint")

        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + timeout
        try:
            async with asyncio.timeout(timeout):
                records = await self._resolver(host, port)
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("provider endpoint DNS resolution timed out") from exc
        except OSError as exc:
            raise httpcore.ConnectError("provider endpoint DNS resolution failed") from exc

        addresses = _allowed_addresses(
            host,
            records,
            allow_private_network=self._allow_private_network,
            loopback_host=self._loopback_host,
        )
        if not addresses:
            raise httpcore.ConnectError("provider endpoint resolved only to untrusted addresses")

        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for address in addresses:
            remaining = None if deadline is None else max(0.0, deadline - loop.time())
            if remaining == 0:
                raise httpcore.ConnectTimeout("provider connection timed out") from last_error
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=remaining,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc

        if isinstance(last_error, httpcore.ConnectTimeout):
            raise last_error
        raise httpcore.ConnectError("could not connect to a trusted provider address") from (
            last_error
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


def create_provider_transport(
    endpoint_url: str,
    *,
    allow_private_network: bool,
) -> httpx.AsyncHTTPTransport:
    """Create HTTPX's normal TLS transport with a policy-enforcing TCP backend."""
    transport = httpx.AsyncHTTPTransport(
        trust_env=False,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    # HTTPX does not expose httpcore's network_backend parameter; wrap its default backend
    # at the connection boundary so the original hostname remains available for TLS SNI.
    pool = cast(Any, transport)._pool
    backend = pool._network_backend
    if not isinstance(backend, httpcore.AsyncNetworkBackend):
        raise RuntimeError("HTTPX did not provide a supported httpcore network backend")
    pool._network_backend = _EndpointNetworkBackend(
        backend,
        urlsplit(endpoint_url).hostname or "",
        allow_private_network=allow_private_network,
    )
    return transport


async def _resolve_addresses(host: str, port: int) -> list[AddressInfo]:
    records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return cast(list[AddressInfo], records)


def _allowed_addresses(
    host: str,
    records: Iterable[AddressInfo],
    *,
    allow_private_network: bool,
    loopback_host: bool,
) -> list[str]:
    host_is_ip = _ip_address(host)
    allowed: list[str] = []
    for record in records:
        sockaddr = record[4]
        if not sockaddr or not isinstance(sockaddr[0], str):
            continue
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if host_is_ip is not None and address != host_is_ip:
            continue
        if loopback_host:
            permitted = address.is_loopback
        else:
            permitted = allow_private_network or _is_global_address(address)
        if permitted:
            normalized = address.compressed
            if normalized not in allowed:
                allowed.append(normalized)
    return allowed


def _ip_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _is_global_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_global


def _is_loopback_host(host: str) -> bool:
    address = _ip_address(host)
    return (
        host == "localhost"
        or host.endswith(".localhost")
        or bool(address is not None and address.is_loopback)
    )


def _normalize_host(host: str) -> str:
    return host.lower().rstrip(".")
