"""FastMCP server exposing yfinance data as MCP tools.

Provides four tools for Claude Desktop and other MCP clients:

- ``get_stock_price`` — latest price snapshot and fundamentals
- ``get_stock_history`` — OHLCV price history
- ``get_fx_rates`` — JPY foreign exchange rates
- ``search_ticker`` — ticker symbol search
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .client import YfinanceClient

mcp = FastMCP("yfinance-mcp")
_client = YfinanceClient()


@mcp.tool()
async def get_stock_price(code: str) -> dict[str, Any]:
    """Get the latest stock price and fundamentals for a TSE-listed stock.

    Args:
        code: 4-digit Tokyo Stock Exchange code (e.g. ``"7203"`` for Toyota).

    Returns:
        Dict of price fields (close, open, high, low, volume, week52_high,
        week52_low) and fundamental fields (trailing_pe, forward_pe,
        price_to_book, market_cap, sector, trailing_eps, dividend_yield).
        On failure, returns ``{"error": "..."}`` with a descriptive message.
    """
    result = await _client.get_stock_price(code)
    if result is None:
        return {"error": f"No data found for code={code} (ticker {code}.T)"}
    return result.__dict__


@mcp.tool()
async def get_stock_history(
    code: str,
    start_date: str,
    end_date: str | None = None,
    interval: str = "1d",
) -> dict[str, Any]:
    """Get OHLCV price history for a TSE-listed stock.

    Args:
        code: 4-digit Tokyo Stock Exchange code (e.g. ``"7203"``).
        start_date: Start date in ``YYYY-MM-DD`` format.
        end_date: End date in ``YYYY-MM-DD`` format (defaults to today).
        interval: Data interval — ``"1d"`` (daily), ``"1wk"`` (weekly),
            ``"1mo"`` (monthly).

    Returns:
        Dict with ``source``, ``ticker``, ``start``, ``end``, ``count``,
        and ``data`` (list of OHLCV row dicts).  On failure, returns
        ``{"error": "..."}`` with a descriptive message.
    """
    result = await _client.get_stock_history(
        code, start_date=start_date, end_date=end_date, interval=interval
    )
    if result is None:
        return {"error": f"No history found for code={code}"}
    return {
        "source": result.source,
        "ticker": result.ticker,
        "start": result.start,
        "end": result.end,
        "count": len(result.rows),
        "data": result.rows,
    }


@mcp.tool()
async def get_fx_rates(pairs: list[str] | None = None) -> dict[str, Any]:
    """Get JPY foreign exchange rates.

    Args:
        pairs: List of currency pair names to fetch.  Available:
            ``USDJPY``, ``EURJPY``, ``GBPJPY``, ``CNYJPY``.
            Defaults to all four if not specified.

    Returns:
        Dict with ``source`` and ``rates`` (mapping of pair name to
        rate value).  On failure, returns ``{"error": "..."}`` with a
        descriptive message.
    """
    result = await _client.get_fx_rates(pairs)
    if result is None:
        return {"error": "Failed to fetch FX rates"}
    return {"source": result.source, "rates": result.rates}


@mcp.tool()
async def search_ticker(query: str) -> list[dict[str, Any]]:
    """Search Yahoo Finance for a stock ticker by company name or keyword.

    Args:
        query: Company name or keyword (e.g. ``"Toyota"``, ``"ソニー"``,
            ``"Nikkei ETF"``).

    Returns:
        List of dicts, each with ``symbol``, ``short_name``, ``long_name``,
        ``exchange``, and ``type``.  If no matches are found, returns a
        single-element list with a ``message`` key.
    """
    results = await _client.search_ticker(query)
    if not results:
        return [{"message": f"No tickers found for query: {query}"}]
    return results
