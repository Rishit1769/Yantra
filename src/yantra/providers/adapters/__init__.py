"""Explicit HTTP protocol adapters for model providers."""

from yantra.providers.adapters.anthropic import AnthropicAdapter
from yantra.providers.adapters.deepseek import DeepSeekAdapter
from yantra.providers.adapters.gemini import GeminiAdapter
from yantra.providers.adapters.generic import GenericOpenAICompatibleAdapter
from yantra.providers.adapters.ollama import OllamaAdapter
from yantra.providers.adapters.openai import OpenAIAdapter
from yantra.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from yantra.providers.adapters.opencode import OpenCodeGoAdapter, OpenCodeZenAdapter
from yantra.providers.adapters.openrouter import OpenRouterAdapter

__all__ = [
    "AnthropicAdapter",
    "DeepSeekAdapter",
    "GeminiAdapter",
    "GenericOpenAICompatibleAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "OpenCodeGoAdapter",
    "OpenCodeZenAdapter",
    "OpenRouterAdapter",
]
