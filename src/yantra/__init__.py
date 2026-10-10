"""YANTRA: model-agnostic agent runtime contracts and adapters."""

from importlib.metadata import PackageNotFoundError, version

from yantra.core.messages import Message, MessageRole, ToolCall, ToolResult
from yantra.providers.gateway import GatewayResponse, ModelGateway
from yantra.providers.mock import MockProvider
from yantra.security.credentials import CredentialManager

try:
    __version__ = version("yantra")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "GatewayResponse",
    "CredentialManager",
    "Message",
    "MessageRole",
    "MockProvider",
    "ModelGateway",
    "ToolCall",
    "ToolResult",
    "__version__",
]
