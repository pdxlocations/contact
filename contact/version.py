"""Application version shared by the CLI and UI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("contact")
except PackageNotFoundError:
    __version__ = "dev"
