import time
from collections.abc import Sequence
from uuid import uuid4

import pytest

from yantra.core.contracts import ModelCapability, ProviderCapabilities, TokenUsage
from yantra.core.errors import (
    DuplicateProviderError,
    ModelIdentifierError,
    ProviderUnavailableError,
    RoutingPolicyError,
)
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.providers.base import ModelRequest
from yantra.providers.catalog import ModelCatalog, ModelCatalogEntry
from yantra.providers.gateway import ModelGateway
from yantra.providers.identifiers import ModelIdentifier
from yantra.providers.mock import MockProvider
from yantra.providers.registry import ProviderAvailability, ProviderRegistry
from yantra.routing.policy import ModelRoutingPolicy


def user_message(text: str = "hello") -> Message:
    return Message(role=MessageRole.USER, content=(TextContent(text=text),))


def test_model_identifier_splits_only_first_slash() -> None:
    identifier = ModelIdentifier.parse("openrouter/anthropic/claude-sonnet-5-5")
    assert identifier.provider_id == "openrouter"
    assert identifier.model_id == "anthropic/claude-sonnet-5-5"
    assert str(identifier) == "openrouter/anthropic/claude-sonnet-5-5"


@pytest.mark.parametrize("value", ["", "model-only", "/model", "provider/", "Bad Provider/model"])
def test_model_identifier_rejects_invalid_reference(value: str) -> None:
    with pytest.raises(ModelIdentifierError):
        ModelIdentifier.parse(value)


def test_registry_detects_duplicate_and_lists_stably() -> None:
    registry = ProviderRegistry()
    registry.register(MockProvider(provider_id="z-provider"))
    registry.register(MockProvider(provider_id="a-provider"))
    assert [item.metadata.provider_id for item in registry.list()] == ["a-provider", "z-provider"]
    with pytest.raises(DuplicateProviderError):
        registry.register(MockProvider(provider_id="a-provider"))


def test_routing_approval_fingerprint_is_stable_after_serialization() -> None:
    policy = ModelRoutingPolicy(
        approved_providers=frozenset({"z-provider", "a-provider"}),
        approved_models=frozenset({"z-provider/model", "a-provider/model"}),
        automatic_enabled=True,
        automatic_model_order=("a-provider/model", "z-provider/model"),
    ).approve()

    restored = ModelRoutingPolicy.model_validate_json(policy.model_dump_json())

    assert restored.optional_routing_approved
    assert restored.approval_fingerprint() == policy.approval_fingerprint()


class CatalogMock(MockProvider):
    def __init__(
        self,
        models: Sequence[ModelCatalogEntry],
        *,
        provider_id: str = "catalog-mock",
        responses=(),
    ) -> None:
        super().__init__(responses, provider_id=provider_id)
        self.models = tuple(models)
        self.discovery_calls = 0

    async def list_models(self) -> tuple[ModelCatalogEntry, ...]:
        self.discovery_calls += 1
        return self.models


@pytest.mark.asyncio
async def test_catalog_caches_and_filters_unknown_capabilities(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr(time, "monotonic", lambda: now)
    model = ModelCatalogEntry(
        provider_id="catalog-mock",
        model_id="model-a",
        capabilities=ProviderCapabilities(tool_calling=True),
    )
    provider = CatalogMock([model])
    registry = ProviderRegistry()
    registry.register(provider)
    catalog = ModelCatalog(registry, ttl_seconds=10)

    assert len(await catalog.list_models("catalog-mock")) == 1
    assert (
        len(
            await catalog.list_models(
                "catalog-mock", required_capabilities=(ModelCapability.TOOL_CALLING,)
            )
        )
        == 1
    )
    assert provider.discovery_calls == 1
    now += 11
    await catalog.list_models("catalog-mock")
    assert provider.discovery_calls == 2


@pytest.mark.asyncio
async def test_manual_gateway_reports_actual_provider_and_model() -> None:
    request_id = uuid4()
    request = ModelRequest(
        request_id=request_id,
        model_id="small-model",
        messages=(user_message(),),
    )
    configured = MockProvider.text_response(
        request,
        "mocked answer",
        provider_id="local-mock",
        usage=TokenUsage(input_tokens=1, output_tokens=2, total_tokens=3),
    )
    provider = MockProvider([configured], provider_id="local-mock")
    registry = ProviderRegistry()
    registry.register(provider, is_local=True)
    gateway = ModelGateway(registry, default_model="local-mock/small-model")

    result = await gateway.complete(request)

    assert result.response.message.content[0].text == "mocked answer"
    assert result.selected_model == "local-mock/small-model"
    assert result.response.provider_id == "local-mock"


@pytest.mark.asyncio
async def test_automatic_routing_requires_digest_bound_approval() -> None:
    request = ModelRequest(model_id="unused", messages=(user_message(),))
    provider = CatalogMock(
        [
            ModelCatalogEntry(
                provider_id="catalog-mock",
                model_id="model-a",
                capabilities=ProviderCapabilities(),
            )
        ]
    )
    registry = ProviderRegistry()
    registry.register(provider)
    policy = ModelRoutingPolicy(
        automatic_enabled=True,
        automatic_model_order=("catalog-mock/model-a",),
    )
    gateway = ModelGateway(registry, routing_policy=policy)
    with pytest.raises(RoutingPolicyError, match="approval"):
        await gateway.complete(request, model="auto")


@pytest.mark.asyncio
async def test_approved_automatic_routing_uses_ordered_catalog() -> None:
    request = ModelRequest(
        model_id="unused",
        messages=(user_message(),),
        required_capabilities=frozenset({ModelCapability.TOOL_CALLING}),
    )
    provider = MockProvider(
        [MockProvider.text_response(request, "selected", provider_id="catalog-mock")],
        provider_id="catalog-mock",
        capabilities=ProviderCapabilities(tool_calling=True),
    )

    async def list_models() -> tuple[ModelCatalogEntry, ...]:
        return (
            ModelCatalogEntry(
                provider_id="catalog-mock",
                model_id="model-a",
                capabilities=ProviderCapabilities(tool_calling=True),
            ),
        )

    provider.list_models = list_models  # type: ignore[method-assign]
    registry = ProviderRegistry()
    registry.register(provider)
    policy = ModelRoutingPolicy(
        automatic_enabled=True,
        automatic_model_order=("catalog-mock/model-a",),
    ).approve()
    result = await ModelGateway(registry, routing_policy=policy).complete(request, model="auto")
    assert result.selected_model == "catalog-mock/model-a"


@pytest.mark.asyncio
async def test_automatic_routing_skips_unavailable_registered_provider() -> None:
    request = ModelRequest(model_id="unused", messages=(user_message(),))
    unavailable = CatalogMock([ModelCatalogEntry(provider_id="catalog-mock", model_id="model-a")])
    available = CatalogMock(
        [ModelCatalogEntry(provider_id="available-mock", model_id="model-b")],
        provider_id="available-mock",
        responses=(MockProvider.text_response(request, "available", provider_id="available-mock"),),
    )
    registry = ProviderRegistry()
    registry.register(unavailable)
    registry.register(available)
    registry.set_availability("catalog-mock", ProviderAvailability.UNAVAILABLE)
    policy = ModelRoutingPolicy(
        automatic_enabled=True,
        automatic_model_order=("catalog-mock/model-a", "available-mock/model-b"),
    ).approve()

    result = await ModelGateway(registry, routing_policy=policy).complete(request, model="auto")

    assert result.selected_model == "available-mock/model-b"
    assert unavailable.discovery_calls == 0


@pytest.mark.asyncio
async def test_approved_fallback_uses_separate_provider_adapter() -> None:
    request = ModelRequest(model_id="model-a", messages=(user_message(),))
    primary = MockProvider(
        [ProviderUnavailableError("offline", provider_id="primary", retryable=True)],
        provider_id="primary",
    )
    fallback_response = MockProvider.text_response(
        request, "fallback response", provider_id="fallback"
    )
    fallback = MockProvider([fallback_response], provider_id="fallback")
    registry = ProviderRegistry()
    registry.register(primary)
    registry.register(fallback)
    policy = ModelRoutingPolicy(
        fallback_enabled=True,
        approved_models=frozenset({"primary/model-a", "fallback/model-b"}),
        fallback_chain=("fallback/model-b",),
    ).approve()

    result = await ModelGateway(registry, routing_policy=policy).complete(
        request, model="primary/model-a"
    )
    assert result.response.message.content[0].text == "fallback response"
    assert result.selected_model == "fallback/model-b"
    assert result.fallback_models == ("fallback/model-b",)
