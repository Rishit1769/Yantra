"""YANTRA: model-agnostic agent runtime contracts and adapters."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yantra")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = ["__version__"]
