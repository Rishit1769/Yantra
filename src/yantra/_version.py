"""Package version shared by the public API and provider transport."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yantra")
except PackageNotFoundError:
    __version__ = "0.1.0"
