"""Locate the packaged GNU flex binary."""

from ._version import __version__
from .paths import get_flex_path

__all__ = ["__version__", "get_flex_path"]
