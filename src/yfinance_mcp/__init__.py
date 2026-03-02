"""yfinance-mcp: Yahoo Finance MCP server for Claude Desktop."""

from .client import FxRates, PriceHistory, StockPrice, YfinanceClient
from .server import mcp

__version__ = "0.1.1"

__all__ = [
    "FxRates",
    "PriceHistory",
    "StockPrice",
    "YfinanceClient",
    "__version__",
    "mcp",
]
