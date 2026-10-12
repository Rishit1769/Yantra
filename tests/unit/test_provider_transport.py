import socket
from typing import Any, cast

import httpcore
import pytest

from yantra.providers._transport import (
    AddressInfo,
    _EndpointNetworkBackend,
    create_provider_transport,
)


class _RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.connected_hosts: list[str] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object | None = None,
    ) -> httpcore.AsyncNetworkStream:
        self.connected_hosts.append(host)
        return cast(httpcore.AsyncNetworkStream, object())

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: object | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise NotImplementedError

    async def sleep(self, seconds: float) -> None:
        raise NotImplementedError


def _address_info(address: str) -> AddressInfo:
    sockaddr: tuple[object, ...] = (address, 443) if ":" not in address else (address, 443, 0, 0)
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


@pytest.mark.asyncio
async def test_default_httpx_transport_uses_endpoint_policy_backend() -> None:
    transport = create_provider_transport(
        "https://provider.example/v1",
        allow_private_network=False,
    )
    pool = cast(Any, transport)._pool

    assert isinstance(pool._network_backend, _EndpointNetworkBackend)
    await transport.aclose()


@pytest.mark.asyncio
async def test_provider_transport_filters_private_dns_addresses_and_pins_public_ip() -> None:
    backend = _RecordingBackend()

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        assert (host, port) == ("provider.example", 443)
        return [_address_info("10.20.30.40"), _address_info("93.184.216.34")]

    policy_backend = _EndpointNetworkBackend(
        backend,
        "provider.example",
        allow_private_network=False,
        resolver=resolver,
    )

    await policy_backend.connect_tcp("provider.example", 443)

    assert backend.connected_hosts == ["93.184.216.34"]


@pytest.mark.asyncio
async def test_provider_transport_rejects_private_dns_resolution_by_default() -> None:
    backend = _RecordingBackend()

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        return [_address_info("10.20.30.40")]

    policy_backend = _EndpointNetworkBackend(
        backend,
        "provider.example",
        allow_private_network=False,
        resolver=resolver,
    )

    with pytest.raises(httpcore.ConnectError, match="untrusted addresses"):
        await policy_backend.connect_tcp("provider.example", 443)

    assert backend.connected_hosts == []


@pytest.mark.asyncio
async def test_provider_transport_rechecks_changed_dns_on_each_connection() -> None:
    backend = _RecordingBackend()
    answers = [[_address_info("93.184.216.34")], [_address_info("10.20.30.40")]]

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        return answers.pop(0)

    policy_backend = _EndpointNetworkBackend(
        backend,
        "provider.example",
        allow_private_network=False,
        resolver=resolver,
    )

    await policy_backend.connect_tcp("provider.example", 443)
    with pytest.raises(httpcore.ConnectError, match="untrusted addresses"):
        await policy_backend.connect_tcp("provider.example", 443)

    assert backend.connected_hosts == ["93.184.216.34"]


@pytest.mark.asyncio
async def test_provider_transport_allows_explicitly_trusted_private_endpoint() -> None:
    backend = _RecordingBackend()

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        return [_address_info("10.20.30.40")]

    policy_backend = _EndpointNetworkBackend(
        backend,
        "inference.internal",
        allow_private_network=True,
        resolver=resolver,
    )

    await policy_backend.connect_tcp("inference.internal", 443)

    assert backend.connected_hosts == ["10.20.30.40"]


@pytest.mark.asyncio
async def test_provider_transport_keeps_loopback_endpoints_loopback_only() -> None:
    backend = _RecordingBackend()

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        return [_address_info("127.0.0.1"), _address_info("93.184.216.34")]

    policy_backend = _EndpointNetworkBackend(
        backend,
        "localhost",
        allow_private_network=True,
        resolver=resolver,
    )

    await policy_backend.connect_tcp("localhost", 11434)

    assert backend.connected_hosts == ["127.0.0.1"]


@pytest.mark.asyncio
async def test_provider_transport_rejects_a_connection_to_another_hostname() -> None:
    backend = _RecordingBackend()

    async def resolver(host: str, port: int) -> list[AddressInfo]:
        raise AssertionError("unexpected DNS lookup")

    policy_backend = _EndpointNetworkBackend(
        backend,
        "provider.example",
        allow_private_network=False,
        resolver=resolver,
    )

    with pytest.raises(httpcore.ConnectError, match="does not match"):
        await policy_backend.connect_tcp("attacker.example", 443)

    assert backend.connected_hosts == []
