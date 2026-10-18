"""YANTRA: model-agnostic agent runtime contracts and adapters."""

from yantra._version import __version__
from yantra.core.messages import Message, MessageRole, ToolCall, ToolResult
from yantra.providers.gateway import GatewayResponse, ModelGateway
from yantra.providers.mock import MockProvider
from yantra.runtime import AgentExecutionEngine, AgentRunConfig, AgentRunResult, CancellationToken
from yantra.security.credentials import CredentialManager

__all__ = [
    "GatewayResponse",
    "AgentExecutionEngine",
    "AgentRunConfig",
    "AgentRunResult",
    "CancellationToken",
    "CredentialManager",
    "Message",
    "MessageRole",
    "MockProvider",
    "ModelGateway",
    "ToolCall",
    "ToolResult",
    "__version__",
]
