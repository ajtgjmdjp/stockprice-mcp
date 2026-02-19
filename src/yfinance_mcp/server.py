"""FastMCP server for yfinance-mcp."""

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
        code: 4-digit Tokyo Stock Exchange code (e.g. "7203" for Toyota)

    Returns:
        Latest close/open/high/low, 52-week range, volume, P/E, P/B, market cap, sector.
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
        code: 4-digit Tokyo Stock Exchange code (e.g. "7203")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (defaults to today)
        interval: Data interval — "1d" (daily), "1wk" (weekly), "1mo" (monthly)

    Returns:
        List of OHLCV rows with date, open, high, low, close, volume.
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
        pairs: List of currency pairs to fetch. Available: USDJPY, EURJPY, GBPJPY, CNYJPY.
               Defaults to all four if not specified.

    Returns:
        Latest exchange rates vs JPY.
    """
    result = await _client.get_fx_rates(pairs)
    if result is None:
        return {"error": "Failed to fetch FX rates"}
    return {"source": result.source, "rates": result.rates}


@mcp.tool()
async def search_ticker(query: str) -> list[dict[str, Any]]:
    """Search Yahoo Finance for a stock ticker by company name or keyword.

    Args:
        query: Company name or keyword (e.g. "Toyota", "ソニー", "Nikkei ETF")

    Returns:
        List of matching tickers with symbol, name, exchange, type.
    """
    results = await _client.search_ticker(query)
    if not results:
        return [{"message": f"No tickers found for query: {query}"}]
    return results
