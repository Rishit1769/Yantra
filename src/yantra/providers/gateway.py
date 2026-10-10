"""Model gateway: capability checks, manual-first routing, bounded retries and fallback."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AbstractContextManager
from decimal import Decimal
from typing import cast

from pydantic import BaseModel, ConfigDict, JsonValue, SecretStr

from yantra.core.contracts import ModelCapability, ProviderCapabilities
from yantra.core.errors import (
    CredentialUnavailableError,
    ExecutionBudgetError,
    ProviderError,
    RoutingPolicyError,
    UnsupportedCapabilityError,
)
from yantra.core.messages import Message, MessageRole, TextContent
from yantra.core.tools_schema import ProviderToolSchema
from yantra.observability.gateway_events import GatewayEvent, GatewayEventType
from yantra.providers.base import (
    GenerationSettings,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    StreamingModelProvider,
    missing_capabilities,
)
from yantra.providers.catalog import ModelCatalog, ModelCatalogEntry
from yantra.providers.identifiers import ModelIdentifier
from yantra.providers.registry import ProviderAvailability, ProviderRegistry
from yantra.providers.retries import RetryPolicy
from yantra.providers.validation import (
    CredentialValidatingProvider,
    CredentialValidationResult,
    CredentialValidationStatus,
)
from yantra.routing.policy import ModelRoutingPolicy, RoutingDecision, RoutingMode
from yantra.security.credentials import CredentialManager

GatewayEventHandler = Callable[[GatewayEvent], Awaitable[None] | None]


class GatewayResponse(BaseModel):
    """Normalized response plus the actual route used for this request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    response: ModelResponse
    selected_model: str
    routing_decision: RoutingDecision
    fallback_models: tuple[str, ...] = ()
    estimated_cost_usd: Decimal | None = None
    provider_reported_cost_usd: Decimal | None = None


class ModelGateway:
    """Model-neutral request entry point independent of an agent execution loop."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        catalog: ModelCatalog | None = None,
        routing_policy: ModelRoutingPolicy | None = None,
        default_model: str | None = None,
        retry_policy: RetryPolicy | None = None,
        event_handler: GatewayEventHandler | None = None,
        credential_manager: CredentialManager | None = None,
    ) -> None:
        self.registry = registry
        self.catalog = catalog or ModelCatalog(registry)
        self.routing_policy = routing_policy or ModelRoutingPolicy()
        self.default_model = default_model
        self.retry_policy = retry_policy or RetryPolicy()
        self.credential_manager = credential_manager or CredentialManager()
        if self.retry_policy.max_attempts > self.routing_policy.max_attempts_per_provider:
            raise RoutingPolicyError(
                "retry policy attempts exceed the configured routing policy limit"
            )
        if self.retry_policy.max_attempts > 1 and not self.routing_policy.optional_routing_approved:
            raise RoutingPolicyError("retries beyond one attempt require routing policy approval")
        self.event_handler = event_handler

    async def validate_credentials(
        self,
        provider_id: str,
        *,
        credential_reference: str | None = None,
        smoke_test_model: str | None = None,
        allow_billable_smoke_test: bool = False,
    ) -> CredentialValidationResult:
        """Validate auth without inference, unless a billable smoke test is explicitly approved."""
        adapter = self.registry.get(provider_id).adapter
        reference = credential_reference or getattr(adapter, "credential_reference", None)
        secret: SecretStr | None = None
        if reference is not None:
            try:
                secret = self.credential_manager.resolve(reference)
            except CredentialUnavailableError as exc:
                result = CredentialValidationResult(
                    provider_id=provider_id,
                    status=CredentialValidationStatus.INVALID,
                    message=exc.message,
                )
                await self._emit_credential_result(result)
                return result

        validator = getattr(adapter, "validate_credentials", None)
        if not callable(validator):
            result = CredentialValidationResult(
                provider_id=provider_id,
                status=CredentialValidationStatus.UNVERIFIED,
                message="adapter has no non-inference credential validation endpoint",
            )
        else:
            result = await cast(CredentialValidatingProvider, adapter).validate_credentials(secret)

        if result.status == CredentialValidationStatus.UNVERIFIED and smoke_test_model is not None:
            if not allow_billable_smoke_test:
                result = result.model_copy(
                    update={
                        "message": result.message
                        + "; minimal inference validation requires explicit billable opt-in"
                    }
                )
            elif secret is None:
                result = result.model_copy(
                    update={"message": "smoke test requires an explicitly resolved credential"}
                )
            else:
                identifier = ModelIdentifier.parse(smoke_test_model)
                if identifier.provider_id != provider_id:
                    raise RoutingPolicyError(
                        "smoke-test model must belong to the provider being validated"
                    )
                smoke_request = ModelRequest(
                    model_id=identifier.model_id,
                    messages=(
                        Message(
                            role=MessageRole.USER,
                            content=(TextContent(text="Reply with OK."),),
                        ),
                    ),
                    generation=GenerationSettings(max_output_tokens=8),
                    estimated_input_tokens=8,
                    timeout_seconds=15,
                )
                registration = self.registry.get(provider_id)
                catalog_entry = await self._catalog_entry_for_cost(identifier, smoke_request)
                self.routing_policy.authorize_model(
                    identifier.reference,
                    is_local=registration.metadata.is_local,
                    estimated_cost_usd=self._maximum_cost(catalog_entry, smoke_request),
                )
                use_credential = getattr(adapter, "use_credential", None)
                if not callable(use_credential):
                    result = result.model_copy(
                        update={"message": "adapter cannot safely inject a one-shot credential"}
                    )
                else:
                    try:
                        credential_scope = cast(
                            Callable[[SecretStr], AbstractContextManager[None]], use_credential
                        )
                        with credential_scope(secret):
                            await adapter.complete(smoke_request)
                    except ProviderError as exc:
                        result = CredentialValidationResult(
                            provider_id=provider_id,
                            status=(
                                CredentialValidationStatus.INVALID
                                if exc.code == "provider_authentication_error"
                                else CredentialValidationStatus.RESTRICTED
                                if exc.code
                                in {"provider_authorization_error", "provider_model_unavailable"}
                                else CredentialValidationStatus.PROVIDER_UNAVAILABLE
                                if exc.retryable
                                else CredentialValidationStatus.UNVERIFIED
                            ),
                            message=exc.message,
                        )
                    else:
                        result = CredentialValidationResult(
                            provider_id=provider_id,
                            status=CredentialValidationStatus.VALID,
                            message=(
                                f"inference smoke test succeeded for {identifier.reference}; "
                                "it may be billable and does not prove access to other models"
                            ),
                        )
        await self._emit_credential_result(result)
        return result

    async def _emit_credential_result(self, result: CredentialValidationResult) -> None:
        await self._emit(
            GatewayEvent(
                event_type=GatewayEventType.CREDENTIAL_VALIDATION,
                provider_id=result.provider_id,
                error_code=result.status.value,
            )
        )

    async def generate(
        self,
        *,
        model: str | None,
        messages: Sequence[Message],
        tools: tuple[ProviderToolSchema, ...] = (),
        required_capabilities: frozenset[ModelCapability] = frozenset(),
        response_schema: dict[str, JsonValue] | None = None,
        generation: GenerationSettings | None = None,
        timeout_seconds: float = 60.0,
        estimated_input_tokens: int | None = None,
        provider_options: dict[str, JsonValue] | None = None,
    ) -> GatewayResponse:
        """Build a normalized request, route it, and return one normalized response."""
        if model is None and self.default_model is None:
            raise RoutingPolicyError("manually select a model or configure a default_model")
        required = set(required_capabilities)
        if tools:
            required.add(ModelCapability.TOOL_CALLING)
        if response_schema:
            required.add(ModelCapability.STRUCTURED_OUTPUT)
        request = ModelRequest(
            model_id=model or self.default_model or "",
            messages=tuple(messages),
            tools=tools,
            required_capabilities=frozenset(required),
            response_schema=response_schema,
            generation=generation or GenerationSettings(),
            timeout_seconds=timeout_seconds,
            estimated_input_tokens=estimated_input_tokens,
            provider_options=provider_options or {},
        )
        return await self.complete(request, model=model)

    async def complete(self, request: ModelRequest, *, model: str | None = None) -> GatewayResponse:
        """Complete one request using the explicit model or configured manual default."""
        requested_model = model or self.default_model or request.model_id
        if requested_model == "auto":
            selected, decision = await self._select_automatic(request)
        else:
            identifier = ModelIdentifier.parse(requested_model)
            entry = await self._catalog_entry_for_cost(identifier, request)
            registration = self.registry.get(identifier.provider_id)
            self.routing_policy.authorize_model(
                identifier.reference,
                is_local=registration.metadata.is_local,
                estimated_cost_usd=self._maximum_cost(entry, request),
            )
            selected = identifier
            decision = RoutingDecision(
                selected_model=identifier.reference,
                mode=RoutingMode.MANUAL,
                reason="explicit model selection",
            )

        response: ModelResponse | None = None
        fallback_models: list[str] = []
        selected_preflight_cost: Decimal | None = None
        registrations = {
            provider.metadata.provider_id: provider for provider in self.registry.list()
        }
        selected_registration = self.registry.get(selected.provider_id)
        candidates = (selected.reference,) + self.routing_policy.approved_fallbacks(
            original=selected.reference,
            original_is_local=selected_registration.metadata.is_local,
            is_local_by_provider={
                provider_id: provider.metadata.is_local
                for provider_id, provider in registrations.items()
            },
        )

        await self._emit(
            GatewayEvent(
                event_type=GatewayEventType.MODEL_SELECTED,
                request_id=request.request_id,
                provider_id=selected.provider_id,
                model_id=selected.model_id,
                reason=decision.reason,
            )
        )

        for index, reference in enumerate(candidates):
            identifier = ModelIdentifier.parse(reference)
            current = request.model_copy(update={"model_id": identifier.model_id})
            registration = self.registry.get(identifier.provider_id)
            if registration.metadata.availability.value == "unavailable":
                if index + 1 < len(candidates):
                    await self._emit(
                        GatewayEvent(
                            event_type=GatewayEventType.FALLBACK,
                            request_id=request.request_id,
                            provider_id=identifier.provider_id,
                            model_id=identifier.model_id,
                            reason="registered provider availability is unavailable",
                        )
                    )
                    continue
                raise RoutingPolicyError(
                    f"provider {identifier.provider_id!r} is marked unavailable"
                )
            entry = await self._catalog_entry_for_cost(identifier, current)
            preflight_cost = self._maximum_cost(entry, current)
            self.routing_policy.authorize_model(
                reference,
                is_local=registration.metadata.is_local,
                estimated_cost_usd=preflight_cost,
            )
            await self._check_capabilities(registration.adapter, current, identifier)
            if index:
                fallback_models.append(reference)
                await self._emit(
                    GatewayEvent(
                        event_type=GatewayEventType.FALLBACK,
                        request_id=request.request_id,
                        provider_id=identifier.provider_id,
                        model_id=identifier.model_id,
                        reason=f"fallback from {candidates[0]}",
                    )
                )
            try:
                response = await self._complete_with_retries(registration.adapter, current)
                selected = identifier
                selected_preflight_cost = preflight_cost
                break
            except ProviderError as exc:
                can_fallback = (
                    index + 1 < len(candidates)
                    and exc.code in _FALLBACK_ERROR_CODES
                    and self.routing_policy.fallback_enabled
                    and self.routing_policy.optional_routing_approved
                )
                if not can_fallback:
                    raise

        if response is None:
            raise ProviderError("no provider returned a model response")

        entry = await self._cached_entry(selected)
        estimated_cost = self._estimate_cost(entry, response)
        if estimated_cost is None:
            estimated_cost = selected_preflight_cost
        reported_cost = response.usage.provider_reported_cost_usd if response.usage else None
        if self.routing_policy.max_estimated_cost_usd is not None:
            checked_cost = reported_cost if reported_cost is not None else estimated_cost
            if checked_cost is None:
                raise ExecutionBudgetError(
                    "cost limit could not be verified because provider usage is unavailable"
                )
            if checked_cost > self.routing_policy.max_estimated_cost_usd:
                raise ExecutionBudgetError(
                    "provider-reported or estimated cost exceeded the configured request limit"
                )
        await self._emit(
            GatewayEvent(
                event_type=GatewayEventType.REQUEST_COMPLETED,
                request_id=request.request_id,
                provider_id=response.provider_id,
                model_id=response.model_id,
                metadata={
                    "usage_available": response.usage is not None,
                    "fallback_count": len(fallback_models),
                },
            )
        )
        return GatewayResponse(
            response=response,
            selected_model=selected.reference,
            routing_decision=decision.model_copy(
                update={
                    "selected_model": selected.reference,
                    "fallback_from": candidates[0] if fallback_models else None,
                }
            ),
            fallback_models=tuple(fallback_models),
            estimated_cost_usd=estimated_cost,
            provider_reported_cost_usd=reported_cost,
        )

    async def stream(
        self,
        request: ModelRequest,
        *,
        model: str | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream normalized events. No failover occurs after the first event is yielded."""
        requested_model = model or self.default_model or request.model_id
        if not requested_model:
            raise RoutingPolicyError("manually select a model or configure a default_model")
        stream_request = request.model_copy(
            update={
                "required_capabilities": request.required_capabilities
                | frozenset({ModelCapability.STREAMING})
            }
        )
        if requested_model == "auto":
            selected, decision = await self._select_automatic(stream_request)
        else:
            selected = ModelIdentifier.parse(requested_model)
            registration = self.registry.get(selected.provider_id)
            entry = await self._catalog_entry_for_cost(selected, request)
            self.routing_policy.authorize_model(
                selected.reference,
                is_local=registration.metadata.is_local,
                estimated_cost_usd=self._maximum_cost(entry, request),
            )
            decision = RoutingDecision(
                selected_model=selected.reference,
                mode=RoutingMode.MANUAL,
                reason="explicit model selection",
            )

        await self._emit(
            GatewayEvent(
                event_type=GatewayEventType.MODEL_SELECTED,
                request_id=request.request_id,
                provider_id=selected.provider_id,
                model_id=selected.model_id,
                reason=decision.reason,
            )
        )

        registrations = {
            provider.metadata.provider_id: provider for provider in self.registry.list()
        }
        selected_registration = self.registry.get(selected.provider_id)
        candidates = (selected.reference,) + self.routing_policy.approved_fallbacks(
            original=selected.reference,
            original_is_local=selected_registration.metadata.is_local,
            is_local_by_provider={
                provider_id: provider.metadata.is_local
                for provider_id, provider in registrations.items()
            },
        )
        for candidate_index, reference in enumerate(candidates):
            identifier = ModelIdentifier.parse(reference)
            registration = self.registry.get(identifier.provider_id)
            if registration.metadata.availability.value == "unavailable":
                if candidate_index + 1 < len(candidates):
                    continue
                raise RoutingPolicyError(
                    f"provider {identifier.provider_id!r} is marked unavailable"
                )
            adapter = registration.adapter
            stream_method = getattr(adapter, "stream", None)
            if not callable(stream_method):
                raise UnsupportedCapabilityError(
                    "selected provider has no streaming implementation",
                    provider_id=identifier.provider_id,
                )
            current = stream_request.model_copy(update={"model_id": identifier.model_id})
            entry = await self._catalog_entry_for_cost(identifier, current)
            preflight_cost = self._maximum_cost(entry, current)
            self.routing_policy.authorize_model(
                reference,
                is_local=registration.metadata.is_local,
                estimated_cost_usd=preflight_cost,
            )
            await self._check_capabilities(adapter, current, identifier)
            emitted = False
            try:
                streaming_adapter = cast(StreamingModelProvider, adapter)
                async for event in streaming_adapter.stream(current):
                    emitted = True
                    if (
                        event.event_type == ModelStreamEventType.USAGE
                        and self.routing_policy.max_estimated_cost_usd is not None
                    ):
                        cost = (
                            event.usage.provider_reported_cost_usd
                            if event.usage is not None
                            else None
                        )
                        if (
                            cost is None
                            and event.usage is not None
                            and entry is not None
                            and entry.pricing
                        ):
                            cost = entry.pricing.estimate(event.usage)
                        if cost is not None and cost > self.routing_policy.max_estimated_cost_usd:
                            raise ExecutionBudgetError(
                                "provider-reported or estimated streaming cost exceeded the limit"
                            )
                    yield event
                return
            except ProviderError as exc:
                if emitted or candidate_index + 1 >= len(candidates):
                    raise
                if exc.code not in _FALLBACK_ERROR_CODES:
                    raise
                continue
        raise ProviderError("no streaming provider returned events")

    async def _complete_with_retries(
        self, adapter: ModelProvider, request: ModelRequest
    ) -> ModelResponse:
        attempt = 1
        while True:
            await self._emit(
                GatewayEvent(
                    event_type=(
                        GatewayEventType.REQUEST_STARTED if attempt == 1 else GatewayEventType.RETRY
                    ),
                    request_id=request.request_id,
                    provider_id=adapter.provider_id,
                    model_id=request.model_id,
                    attempt=attempt,
                )
            )
            try:
                response = await adapter.complete(request)
                if response.request_id != request.request_id:
                    raise ProviderError(
                        "provider response request ID did not match the request",
                        provider_id=adapter.provider_id,
                    )
                if response.provider_id != adapter.provider_id:
                    raise ProviderError(
                        "provider response identity did not match the registered adapter",
                        provider_id=adapter.provider_id,
                    )
                return response
            except ProviderError as exc:
                await self._emit(
                    GatewayEvent(
                        event_type=GatewayEventType.REQUEST_FAILED,
                        request_id=request.request_id,
                        provider_id=adapter.provider_id,
                        model_id=request.model_id,
                        error_code=exc.code,
                        attempt=attempt,
                    )
                )
                if self.retry_policy.can_retry(exc, attempt):
                    await self.retry_policy.wait(exc, attempt)
                    attempt += 1
                    continue
                raise

    async def _check_capabilities(
        self, adapter: ModelProvider, request: ModelRequest, identifier: ModelIdentifier
    ) -> None:
        capability_resolver = getattr(adapter, "capabilities_for", None)
        if callable(capability_resolver):
            candidate_capabilities = capability_resolver(identifier.model_id)
            adapter_capabilities = (
                candidate_capabilities
                if isinstance(candidate_capabilities, ProviderCapabilities)
                else adapter.capabilities
            )
        else:
            adapter_capabilities = adapter.capabilities
        catalog_entry = await self.catalog.peek(identifier.reference)
        if catalog_entry is None:
            capabilities = adapter_capabilities
        else:
            catalog_capabilities = catalog_entry.capabilities
            capabilities = ProviderCapabilities(
                tool_calling=(
                    catalog_capabilities.tool_calling
                    if catalog_capabilities.tool_calling is not None
                    else adapter_capabilities.tool_calling
                ),
                structured_output=(
                    catalog_capabilities.structured_output
                    if catalog_capabilities.structured_output is not None
                    else adapter_capabilities.structured_output
                ),
                streaming=(
                    catalog_capabilities.streaming
                    if catalog_capabilities.streaming is not None
                    else adapter_capabilities.streaming
                ),
                token_usage=(
                    catalog_capabilities.token_usage
                    if catalog_capabilities.token_usage is not None
                    else adapter_capabilities.token_usage
                ),
                cancellation=(
                    catalog_capabilities.cancellation
                    if catalog_capabilities.cancellation is not None
                    else adapter_capabilities.cancellation
                ),
                context_window_tokens=(
                    catalog_entry.context_window_tokens
                    if catalog_entry.context_window_tokens is not None
                    else adapter_capabilities.context_window_tokens
                ),
            )
        missing = missing_capabilities(capabilities, request.required_capabilities)
        if missing:
            names = ", ".join(sorted(capability.value for capability in missing))
            raise UnsupportedCapabilityError(
                f"provider {identifier.provider_id!r} does not declare required capabilities: "
                f"{names}",
                provider_id=identifier.provider_id,
            )

    async def _select_automatic(
        self, request: ModelRequest
    ) -> tuple[ModelIdentifier, RoutingDecision]:
        provider_ids = tuple(
            dict.fromkeys(
                ModelIdentifier.parse(reference).provider_id
                for reference in self.routing_policy.automatic_model_order
            )
        )
        candidates: list[ModelCatalogEntry] = []
        for provider_id in provider_ids:
            registration = self.registry.get(provider_id)
            if registration.metadata.availability == ProviderAvailability.UNAVAILABLE:
                continue
            candidates.extend(await self.catalog.list_models(provider_id))
        is_local = {
            provider.metadata.provider_id: provider.metadata.is_local
            for provider in self.registry.list()
        }
        selected = self.routing_policy.choose_automatic(
            candidates,
            required_capabilities=request.required_capabilities,
            is_local_by_provider=is_local,
            estimated_input_tokens=request.estimated_input_tokens,
            max_output_tokens=request.generation.max_output_tokens,
        )[0]
        identifier = ModelIdentifier(provider_id=selected.provider_id, model_id=selected.model_id)
        return identifier, RoutingDecision(
            selected_model=identifier.reference,
            mode=RoutingMode.AUTOMATIC,
            reason="first approved model meeting capability, privacy, and cost filters",
        )

    async def _catalog_entry_for_cost(
        self, identifier: ModelIdentifier, request: ModelRequest
    ) -> ModelCatalogEntry | None:
        if self.routing_policy.max_estimated_cost_usd is None:
            return await self.catalog.peek(identifier.reference)
        entry = await self.catalog.get(identifier.reference, refresh=True)
        if entry is None:
            raise RoutingPolicyError(
                "cannot enforce cost limit because model pricing metadata is unavailable"
            )
        return entry

    async def _cached_entry(self, identifier: ModelIdentifier) -> ModelCatalogEntry | None:
        return await self.catalog.peek(identifier.reference)

    @staticmethod
    def _maximum_cost(entry: ModelCatalogEntry | None, request: ModelRequest) -> Decimal | None:
        if entry is None or entry.pricing is None:
            return None
        if request.estimated_input_tokens is None or request.generation.max_output_tokens is None:
            return None
        return entry.pricing.estimate_maximum(
            input_tokens=request.estimated_input_tokens,
            output_tokens=request.generation.max_output_tokens,
        )

    @staticmethod
    def _estimate_cost(entry: ModelCatalogEntry | None, response: ModelResponse) -> Decimal | None:
        if response.usage is None or entry is None or entry.pricing is None:
            return None
        return entry.pricing.estimate(response.usage)

    async def _emit(self, event: GatewayEvent) -> None:
        if self.event_handler is None:
            return
        result = self.event_handler(event)
        if inspect.isawaitable(result):
            await result


_FALLBACK_ERROR_CODES = frozenset(
    {
        "provider_rate_limited",
        "provider_timeout",
        "provider_unavailable",
        "provider_network_error",
        "provider_model_unavailable",
    }
)
