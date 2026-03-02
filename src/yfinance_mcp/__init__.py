"""yfinance-mcp: Yahoo Finance MCP server for Claude Desktop."""

from .client import FxRates, PriceHistory, StockPrice, YfinanceClient

__version__ = "0.2.0"

__all__ = [
    "FxRates",
    "PriceHistory",
    "StockPrice",
    "YfinanceClient",
    "__version__",
]

# Library-safe logging: silent by default, let consumers configure.
import logging as _logging

_logging.getLogger(__name__).addHandler(_logging.NullHandler())


def __getattr__(name: str) -> object:
    """Lazy import for optional server components."""
    if name == "mcp":
        from .server import mcp

        return mcp
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
