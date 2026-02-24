"""Command-line interface for yfinance-mcp.

Provides Click commands for querying stock prices, OHLCV history,
FX rates, and ticker search, plus an MCP server launcher.
"""

from __future__ import annotations

import asyncio
import json

import click

from .client import YfinanceClient


@click.group()
def cli() -> None:
    """yfinance-mcp: Yahoo Finance MCP server and CLI."""


@cli.command()
@click.argument("code")
def price(code: str) -> None:
    """Get latest stock price for a TSE-listed stock (e.g. 7203).

    Args:
        code: 4-digit TSE stock code.

    Raises:
        SystemExit: If no data is found for the given code.
    """
    client = YfinanceClient()
    result = asyncio.run(client.get_stock_price(code))
    if result is None:
        click.echo(f"No data found for {code}", err=True)
        raise SystemExit(1)
    click.echo(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


@cli.command()
@click.argument("code")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", default=None, help="End date YYYY-MM-DD (default: today)")
@click.option("--interval", default="1d", help="1d / 1wk / 1mo")
def history(code: str, start: str, end: str | None, interval: str) -> None:
    """Get OHLCV price history for a TSE-listed stock.

    Args:
        code: 4-digit TSE stock code.
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format, or ``None`` for today.
        interval: Data interval (``"1d"``, ``"1wk"``, or ``"1mo"``).

    Raises:
        SystemExit: If no history is found for the given code and range.
    """
    client = YfinanceClient()
    result = asyncio.run(
        client.get_stock_history(
            code, start_date=start, end_date=end, interval=interval
        )
    )
    if result is None:
        click.echo(f"No history found for {code}", err=True)
        raise SystemExit(1)
    click.echo(json.dumps(
        {"ticker": result.ticker, "start": result.start, "end": result.end, "data": result.rows},
        ensure_ascii=False, indent=2
    ))


@cli.command()
@click.option("--pairs", default=None, help="Comma-separated pairs e.g. USDJPY,EURJPY")
def fx(pairs: str | None) -> None:
    """Get JPY FX rates (USDJPY, EURJPY, GBPJPY, CNYJPY).

    Args:
        pairs: Comma-separated pair names (e.g. ``"USDJPY,EURJPY"``),
            or ``None`` to fetch all four.

    Raises:
        SystemExit: If FX rate fetching fails entirely.
    """
    client = YfinanceClient()
    pair_list = pairs.split(",") if pairs else None
    result = asyncio.run(client.get_fx_rates(pair_list))
    if result is None:
        click.echo("Failed to fetch FX rates", err=True)
        raise SystemExit(1)
    click.echo(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


@cli.command()
@click.argument("query")
def search(query: str) -> None:
    """Search for a ticker by company name or keyword.

    Args:
        query: Company name or keyword to search.
    """
    client = YfinanceClient()
    results = asyncio.run(client.search_ticker(query))
    click.echo(json.dumps(results, ensure_ascii=False, indent=2))


@cli.command()
def test() -> None:
    """Run a quick connectivity test."""
    async def _test() -> None:
        client = YfinanceClient()
        click.echo("Testing stock price (Toyota 7203)...")
        stock = await client.get_stock_price("7203")
        if stock:
            click.echo(f"  ✓ close={stock.close}, date={stock.date}")
        else:
            click.echo("  ✗ failed", err=True)

        click.echo("Testing FX rates...")
        fx_result = await client.get_fx_rates(["USDJPY"])
        if fx_result:
            click.echo(f"  ✓ USDJPY={fx_result.rates.get('USDJPY')}")
        else:
            click.echo("  ✗ failed", err=True)

    asyncio.run(_test())


@cli.command()
def serve() -> None:
    """Start the MCP server over stdio."""
    from .server import mcp
    mcp.run()
